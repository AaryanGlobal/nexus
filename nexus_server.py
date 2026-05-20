#!/usr/bin/env python3
"""
Nexus Agent Integration Server

Provides:
1. HTTP API for agent communication
2. WebSocket for real-time updates (optional)
3. Integration with Hermes and PI

Usage:
    python nexus_server.py [--port 8080]
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

# Add package to path
sys.path.insert(0, str(Path(__file__).parent / "packages" / "core" / "src"))

from hermes_pi_bridge_core.bridge import AgentBridge, AgentType, get_bridge as _get_bridge
from hermes_pi_bridge_core.life_context import LifeContextEngine
from hermes_pi_bridge_core.config import get_config

# Create bridge with correct PI URL (8645, not 9999)
_bridge = AgentBridge(pi_url="http://localhost:8645")

def get_bridge() -> AgentBridge:
    return _bridge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NexusAPIHandler(BaseHTTPRequestHandler):
    """HTTP handler for Nexus API."""
    
    def do_GET(self):
        """Handle GET requests."""
        path = self.path
        
        if path == "/health":
            self.send_json({"status": "ok", "time": datetime.now().isoformat()})
            
        elif path == "/status":
            config = get_config()
            life = LifeContextEngine()
            
            self.send_json({
                "bridge": _bridge.get_connection_status(),
                "config": config.get_status(),
                "life": life.get_status()
            })
            
        elif path == "/connections":
            bridge = get_bridge()
            self.send_json(bridge.get_connection_status())
            
        elif path == "/messages":
            bridge = get_bridge()
            self.send_json(bridge.get_message_history(limit=50))
            
        elif path == "/context":
            bridge = get_bridge()
            self.send_json(bridge.shared_context)
            
        elif path == "/life":
            life = LifeContextEngine()
            self.send_json(life.get_status())
            
        else:
            self.send_error(404, "Not found")
    
    def do_POST(self):
        """Handle POST requests."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"
        
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        
        path = self.path
        
        if path == "/connect":
            agent = data.get("agent")
            url = data.get("url")
            auth = data.get("auth")
            quick = data.get("quick", True)
            
            if agent == "hermes":
                success = _bridge.connect(AgentType.HERMES, url, auth, quick=quick)
            elif agent == "pi":
                success = _bridge.connect(AgentType.PI, url, auth, quick=quick)
            else:
                success = False
            
            self.send_json({"success": success})
            
        elif path == "/delegate":
            to_agent = data.get("to")
            task = data.get("task")
            
            agent_type = AgentType.HERMES if to_agent == "hermes" else AgentType.PI
            
            task_id = _bridge.delegate_task(agent_type, task)
            self.send_json({"task_id": task_id, "success": task_id is not None})
            
        elif path == "/result":
            from_agent = data.get("from")
            result = data.get("result")
            
            agent_type = AgentType.HERMES if from_agent == "hermes" else AgentType.PI
            
            _bridge.receive_result(agent_type, result)
            self.send_json({"success": True})
            
        elif path == "/sync":
            bridge = get_bridge()
            context = data.get("context", {})
            
            for key, value in context.items():
                _bridge.update_shared_context(key, value)
            
            self.send_json({"success": True})
            
        elif path == "/context":
            bridge = get_bridge()
            key = data.get("key")
            value = data.get("value")
            
            _bridge.update_shared_context(key, value)
            self.send_json({"success": True})
            
        else:
            self.send_error(404, "Not found")
    
    def send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def log_message(self, format, *args):
        """Custom log format."""
        logger.info(f"{self.address_string()} - {format % args}")


def run_server(port: int = 8080):
    """Run the Nexus API server."""
    server = HTTPServer(('0.0.0.0', port), NexusAPIHandler)
    logger.info(f"Nexus API server running on port {port}")
    logger.info(f"  Health: http://localhost:{port}/health")
    logger.info(f"  Status: http://localhost:{port}/status")
    logger.info(f"  Connect: POST /connect with {{'agent': 'hermes'|'pi', 'url': '...'}}")
    logger.info(f"  Delegate: POST /delegate with {{'to': 'hermes'|'pi', 'task': {{...}}}}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped")
        server.shutdown()


def main():
    parser = argparse.ArgumentParser(description="Nexus Agent Integration Server")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port to run on")
    
    args = parser.parse_args()
    run_server(args.port)


if __name__ == "__main__":
    main()