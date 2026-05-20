#!/usr/bin/env python3
"""
Nexus Control Panel - Web-based management dashboard
Provides a web UI for managing Nexus system
"""
import json
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

sys.path.insert(0, str(Path(__file__).parent / "packages" / "core" / "src"))

from hermes_pi_bridge_core.bridge import get_bridge, AgentType
from hermes_pi_bridge_core.life_context import LifeContextEngine
from hermes_pi_bridge_core.config import get_config


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nexus Control Panel</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #58a6ff; margin-bottom: 20px; border-bottom: 1px solid #30363d; padding-bottom: 10px; }
        h2 { color: #8b949e; margin: 20px 0 10px; font-size: 1.1em; text-transform: uppercase; letter-spacing: 1px; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 20px; margin-bottom: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .stat { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #21262d; }
        .stat:last-child { border-bottom: none; }
        .label { color: #8b949e; }
        .value { color: #58a6ff; font-weight: 600; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; }
        .badge-connected { background: #238636; color: white; }
        .badge-disconnected { background: #6e7681; color: white; }
        .btn { background: #238636; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; margin: 5px; }
        .btn:hover { background: #2ea043; }
        .btn-danger { background: #da3633; }
        .btn-danger:hover { background: #f85149; }
        .capability { display: inline-block; background: #21262d; padding: 4px 10px; border-radius: 4px; margin: 3px; font-size: 0.85em; }
        .pillar { background: #1f6feb17; border-left: 3px solid #1f6feb; padding: 10px 15px; margin: 10px 0; }
        .pillar-name { font-weight: 600; color: #58a6ff; }
        .timestamp { color: #6e7681; font-size: 0.85em; }
        .refresh { float: right; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Nexus Control Panel <button class="btn" onclick="location.reload()">↻ Refresh</button></h1>
        
        <div class="grid">
            <div class="card">
                <h2>Agent Bridges</h2>
                <div class="stat">
                    <span class="label">Hermes</span>
                    <span class="badge {bridges.hermes.badge_class}">{bridges.hermes.status}</span>
                </div>
                <div class="stat">
                    <span class="label">PI</span>
                    <span class="badge {bridges.pi.badge_class}">{bridges.pi.status}</span>
                </div>
                <div class="stat">
                    <span class="label">Last Update</span>
                    <span class="timestamp">{timestamp}</span>
                </div>
            </div>
            
            <div class="card">
                <h2>Capabilities</h2>
                <div class="stat">
                    <span class="label">Hermes</span>
                    <span class="value">{capabilities.hermes} skills</span>
                </div>
                <div class="stat">
                    <span class="label">PI</span>
                    <span class="value">{capabilities.pi} skills</span>
                </div>
                <div style="margin-top: 15px;">
                    {hermes_caps}
                </div>
                <div style="margin-top: 10px;">
                    {pi_caps}
                </div>
            </div>
            
            <div class="card">
                <h2>System Configuration</h2>
                <div class="stat">
                    <span class="label">Version</span>
                    <span class="value">{config.version}</span>
                </div>
                <div class="stat">
                    <span class="label">Rate Limit</span>
                    <span class="value">{config.rate_limit}/min</span>
                </div>
                <div class="stat">
                    <span class="label">Min Confidence</span>
                    <span class="value">{config.min_confidence}</span>
                </div>
                <div class="stat">
                    <span class="label">Learning Rate</span>
                    <span class="value">{config.learning_rate}</span>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>Life Pillars</h2>
            {pillars}
        </div>
        
        <div class="card">
            <h2>Goals</h2>
            <div class="stat">
                <span class="label">Total Goals</span>
                <span class="value">{goals.total}</span>
            </div>
            <div class="stat">
                <span class="label">Completed</span>
                <span class="value">{goals.completed}</span>
            </div>
            <div class="stat">
                <span class="label">Pending Votes</span>
                <span class="value">{goals.pending_votes}</span>
            </div>
        </div>
        
        <div class="card">
            <h2>Management</h2>
            <button class="btn" onclick="fetch('/connect/hermes', {method:'POST'}).then(()=>location.reload())">Connect Hermes</button>
            <button class="btn" onclick="fetch('/connect/pi', {method:'POST'}).then(()=>location.reload())">Connect PI</button>
            <button class="btn btn-danger" onclick="fetch('/discover', {method:'POST'}).then(()=>location.reload())">Rediscover Capabilities</button>
        </div>
    </div>
</body>
</html>"""


def get_status_data():
    """Get current status for the dashboard."""
    bridge = get_bridge()
    engine = LifeContextEngine()
    config = get_config()
    
    bridge_status = bridge.get_connection_status()
    life_status = engine.get_status()
    
    h_caps = engine.get_capabilities("hermes")
    p_caps = engine.get_capabilities("pi")
    
    return {
        "bridges": {
            "hermes": {
                "status": bridge_status["hermes"]["status"],
                "badge_class": "badge-connected" if bridge_status["hermes"]["status"] == "connected" else "badge-disconnected"
            },
            "pi": {
                "status": bridge_status["pi"]["status"],
                "badge_class": "badge-connected" if bridge_status["pi"]["status"] == "connected" else "badge-disconnected"
            }
        },
        "capabilities": {
            "hermes": len(h_caps),
            "pi": len(p_caps)
        },
        "hermes_caps": " ".join([f'<span class="capability">{c}</span>' for c in h_caps]),
        "pi_caps": " ".join([f'<span class="capability">{c}</span>' for c in p_caps]),
        "config": {
            "version": config.get_status()["version"],
            "rate_limit": config.get_status()["rate_limit"]["per_minute"],
            "min_confidence": config.get_status()["governance"]["min_confidence"],
            "learning_rate": config.get_status()["rl"]["learning_rate"]
        },
        "pillars": life_status.get("pillars", {}),
        "goals": {
            "total": life_status["goals_total"],
            "completed": life_status["goals_completed"],
            "pending_votes": life_status["pending_votes"]
        },
        "timestamp": __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP handler for dashboard."""
    
    def do_GET(self):
        """Serve dashboard."""
        if self.path == "/" or self.path == "/dashboard":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            
            data = get_status_data()
            html = HTML_TEMPLATE.format(**data)
            self.wfile.write(html.encode())
            
        elif self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            bridge = get_bridge()
            engine = LifeContextEngine()
            config = get_config()
            
            import datetime
            response = {
                "bridge": bridge.get_connection_status(),
                "config": config.get_status(),
                "life": engine.get_status(),
                "timestamp": datetime.datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Handle management commands."""
        if self.path.startswith("/connect/"):
            agent = self.path.split("/")[-1]
            bridge = get_bridge()
            
            if agent == "hermes":
                bridge.connect(AgentType.HERMES)
            elif agent == "pi":
                bridge.connect(AgentType.PI)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "agent": agent}).encode())
            
        elif self.path == "/discover":
            engine = LifeContextEngine()
            engine.discover_capabilities("hermes")
            engine.discover_capabilities("pi")
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())
            
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        """Suppress logging."""
        pass


def run_dashboard(port=8081):
    """Run the dashboard server."""
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"Nexus Control Panel running at http://localhost:{port}/")
    print(f"API endpoint: http://localhost:{port}/api/status")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Nexus Control Panel")
    parser.add_argument("--port", "-p", type=int, default=8081, help="Dashboard port")
    args = parser.parse_args()
    run_dashboard(args.port)