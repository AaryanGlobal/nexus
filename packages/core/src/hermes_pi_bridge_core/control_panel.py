"""
Persistent Iteration Control Panel
===================================

Provides a web-based dashboard and CLI for managing the callback chain
that enables true persistent iteration between Hermes and Pi.

Usage:
    python control_panel.py                    # Start web UI
    python control_panel.py status              # Show status
    python control_panel.py register cb.py     # Register callback
    python control_panel.py webhook URL        # Add webhook
"""

from __future__ import annotations

import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Bridge Status
# =============================================================================

def get_bridge_status() -> dict[str, Any]:
    """Get comprehensive bridge status."""
    try:
        from hermes_pi_bridge_core.bridge import get_bridge
        from hermes_pi_bridge_core.callback import get_callback_registry
        
        bridge = get_bridge()
        registry = get_callback_registry()
        
        return {
            "bridge_connected": True,
            "callbacks_registered": len(bridge._result_callbacks),
            "webhook_endpoints": len(bridge._webhook_dispatcher.channels),
            "callback_events": len(registry._handlers),
            "notification_stats": bridge.get_notification_stats(),
            "message_history_count": len(bridge.message_history),
            "shared_context_keys": list(bridge.shared_context.keys()),
        }
    except ImportError as e:
        return {"error": f"Bridge not available: {e}"}


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Persistent Iteration Control Panel"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Status command
    _status_parser = subparsers.add_parser("status", help="Show bridge status")
    
    # Register callback
    reg_parser = subparsers.add_parser("register", help="Register a callback")
    reg_parser.add_argument("file", help="Python file with callback function")
    
    # Add webhook
    webhook_parser = subparsers.add_parser("webhook", help="Add webhook endpoint")
    webhook_parser.add_argument("endpoint", help="Webhook URL")
    
    # List callbacks
    _list_parser = subparsers.add_parser("list", help="List registered callbacks")
    
    # Server command
    server_parser = subparsers.add_parser("serve", help="Start web UI")
    server_parser.add_argument("--port", type=int, default=9000)
    
    args = parser.parse_args()
    
    if args.command == "status":
        status = get_bridge_status()
        print(json.dumps(status, indent=2))
        
    elif args.command == "register":
        print(f"Would register callback from: {args.file}")
        # In full impl, would load and register the callback
        
    elif args.command == "webhook":
        print(f"Would add webhook: {args.endpoint}")
        # In full impl, would add the webhook
        
    elif args.command == "list":
        status = get_bridge_status()
        print("Registered Callbacks:")
        print(json.dumps(status, indent=2))
        
    elif args.command == "serve":
        start_web_ui(args.port)
        
    else:
        # Default: show status
        status = get_bridge_status()
        print(json.dumps(status, indent=2))


def start_web_ui(port: int = 9000):
    """Start the web UI for control panel."""
    
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/status":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                
                status = get_bridge_status()
                self.wfile.write(json.dumps(status, indent=2).encode())
                
            elif self.path == "/callbacks":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                
                try:
                    from hermes_pi_bridge_core.bridge import get_bridge
                    bridge = get_bridge()
                    callbacks = [
                        {"name": getattr(cb, '__name__', str(cb))}
                        for cb in bridge._result_callbacks
                    ]
                    self.wfile.write(json.dumps({"callbacks": callbacks}, indent=2).encode())
                except Exception as e:
                    self.wfile.write(json.dumps({"error": str(e)}).encode())
                    
            elif self.path == "/webhooks":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                
                try:
                    from hermes_pi_bridge_core.bridge import get_bridge
                    bridge = get_bridge()
                    self.wfile.write(json.dumps({
                        "webhooks": bridge._webhook_dispatcher.channels
                    }, indent=2).encode())
                except Exception as e:
                    self.wfile.write(json.dumps({"error": str(e)}).encode())
                    
            else:
                self.send_error(404)
        
        def do_POST(self):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return
            
            if self.path == "/webhook":
                endpoint = data.get("endpoint")
                if endpoint:
                    try:
                        from hermes_pi_bridge_core.bridge import get_bridge
                        bridge = get_bridge()
                        bridge.add_webhook_endpoint(endpoint)
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"added": endpoint}).encode())
                    except Exception as e:
                        self.send_response(500)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode())
                else:
                    self.send_error(400, "Missing endpoint")
            else:
                self.send_error(404)
        
        def log_message(self, format, *args):
            logger.info(f"{self.address_string()} - {format % args}")
    
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Control Panel running at http://localhost:{port}")
    print("  GET  /status     - Bridge status")
    print("  GET  /callbacks  - List callbacks")
    print("  GET  /webhooks   - List webhooks")
    print("  POST /webhook    - Add webhook (body: {endpoint})")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()