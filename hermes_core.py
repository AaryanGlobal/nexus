"""
Hermes Core - Task Orchestration Server

This is the server-side component that:
1. Receives delegated tasks from Pi
2. Processes them (or queues for sub-agents)
3. Pushes results via WebSocket back to Pi
4. Exposes API for Hermes (user) to poll/check status

Usage:
    python hermes_core.py [--port 8080]
"""

import argparse
import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from collections import defaultdict

import sys
sys.path.insert(0, str(Path(__file__).parent / "packages" / "core" / "src"))

import logging
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Task:
    """Represents a delegated task."""
    task_id: str
    kanban_id: str
    title: str
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    artifacts: list = field(default_factory=list)
    retry_count: int = 0
    metadata: dict = field(default_factory=dict)


class HermesCore:
    """
    Core orchestration server for Hermes-Pi Bridge.
    
    Responsibilities:
    - Task queue management
    - WebSocket push to connected Pi clients
    - HTTP API for Pi and Hermes (user)
    - Result storage and retrieval
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.tasks: dict[str, Task] = {}
        self.pending_queue: list[str] = []  # kanban_ids waiting for processing
        self.processing: dict[str, Task] = {}  # currently processing
        self.completed: dict[str, Task] = {}  # finished tasks
        
        # WebSocket connections (Pi clients)
        self.ws_connections: dict[str, Any] = {}
        
        # Result handlers (for callbacks)
        self.result_handlers: list[callable] = []
        
        # Callbacks (ACP or HTTP webhooks)
        self.callback_urls: list[str] = []
        
        logger.info(f"HermesCore initialized on {host}:{port}")
    
    def register_callback(self, url: str) -> None:
        """Register a callback URL to be notified when tasks complete."""
        if url not in self.callback_urls:
            self.callback_urls.append(url)
            logger.info(f"Callback registered: {url}")
    
    def unregister_callback(self, url: str) -> None:
        """Remove a callback URL."""
        if url in self.callback_urls:
            self.callback_urls.remove(url)
            logger.info(f"Callback unregistered: {url}")
    
    def _invoke_callbacks(self, task: Task):
        """Invoke all registered callbacks with task result."""
        payload = {
            "type": "task_completed",
            "kanban_id": task.kanban_id,
            "task_id": task.task_id,
            "title": task.title,
            "status": task.status.value,
            "result": task.result,
            "artifacts": task.artifacts,
            "completed_at": task.completed_at,
            "error": task.error,
        }
        
        for url in self.callback_urls:
            try:
                self._send_callback(url, payload)
            except Exception as e:
                logger.warning(f"Callback to {url} failed: {e}")
    
    def _send_callback(self, url: str, payload: dict):
        """Send callback to URL via HTTP POST."""
        import urllib.request
        import urllib.error
        
        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                logger.info(f"Callback sent to {url}: {response.status}")
        except urllib.error.HTTPError as e:
            logger.warning(f"Callback to {url} failed with {e.code}: {e.reason}")
        except Exception as e:
            logger.error(f"Callback to {url} failed: {e}")
    
    # === TASK MANAGEMENT ===
    
    def create_task(self, title: str, description: str, priority: str = "normal", 
                    context: dict = None) -> Task:
        """Create a new task."""
        task_id = str(uuid.uuid4())
        kanban_id = f"hermes-{int(time.time())}-{task_id[:8]}"
        
        task = Task(
            task_id=task_id,
            kanban_id=kanban_id,
            title=title[:50],  # truncate title
            description=description,
            priority=TaskPriority(priority),
            metadata={"context": context or {}}
        )
        
        self.tasks[kanban_id] = task
        self.pending_queue.append(kanban_id)
        
        logger.info(f"Task created: {kanban_id}")
        return task
    
    def get_task(self, kanban_id: str) -> Optional[Task]:
        """Get task by kanban_id."""
        return self.tasks.get(kanban_id)
    
    def get_pending_tasks(self) -> list[Task]:
        """Get all pending tasks."""
        return [self.tasks[k] for k in self.pending_queue if k in self.tasks]
    
    def get_completed_tasks(self, since_minutes: int = None) -> list[Task]:
        """Get completed tasks, optionally filtered by time."""
        tasks = list(self.completed.values())
        
        if since_minutes:
            cutoff = datetime.now().timestamp() - (since_minutes * 60)
            tasks = [t for t in tasks if t.completed_at and 
                     datetime.fromisoformat(t.completed_at).timestamp() > cutoff]
        
        return sorted(tasks, key=lambda t: t.completed_at or "", reverse=True)
    
    def get_results_since(self, since_timestamp: float) -> list[dict]:
        """Get results for tasks completed since timestamp. For polling."""
        results = []
        for task in self.completed.values():
            if task.completed_at:
                completed_ts = datetime.fromisoformat(task.completed_at).timestamp()
                if completed_ts > since_timestamp:
                    results.append({
                        "kanban_id": task.kanban_id,
                        "status": task.status.value,
                        "title": task.title,
                        "result": task.result,
                        "artifacts": task.artifacts,
                        "completed_at": task.completed_at,
                    })
        return results
    
    def complete_task(self, kanban_id: str, result: dict, artifacts: list = None) -> bool:
        """Mark task as completed and notify."""
        task = self.tasks.get(kanban_id)
        if not task:
            return False
        
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now().isoformat()
        task.result = result
        task.artifacts = artifacts or []
        
        # Move to completed
        if kanban_id in self.pending_queue:
            self.pending_queue.remove(kanban_id)
        if kanban_id in self.processing:
            del self.processing[kanban_id]
        self.completed[kanban_id] = task
        
        # Push to Pi via WebSocket
        self._push_task_result(task)
        
        # Call registered handlers
        self._notify_result_handlers(task)
        
        # Invoke callbacks (ACP/webhook to Hermes user)
        self._invoke_callbacks(task)
        
        logger.info(f"Task completed: {kanban_id}")
        return True
    
    def fail_task(self, kanban_id: str, error: str) -> bool:
        """Mark task as failed."""
        task = self.tasks.get(kanban_id)
        if not task:
            return False
        
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now().isoformat()
        task.error = error
        
        # Move to completed (failed tasks also go to completed)
        if kanban_id in self.pending_queue:
            self.pending_queue.remove(kanban_id)
        if kanban_id in self.processing:
            del self.processing[kanban_id]
        self.completed[kanban_id] = task
        
        # Push failure notification
        self._push_task_result(task)
        
        logger.warning(f"Task failed: {kanban_id} - {error}")
        return True
    
    # === WEBSOCKET PUSH ===
    
    def register_ws_connection(self, client_id: str, ws):
        """Register a Pi WebSocket client."""
        self.ws_connections[client_id] = ws
        logger.info(f"Pi client connected: {client_id}")
    
    def unregister_ws_connection(self, client_id: str):
        """Unregister a Pi WebSocket client."""
        if client_id in self.ws_connections:
            del self.ws_connections[client_id]
            logger.info(f"Pi client disconnected: {client_id}")
    
    def _push_task_result(self, task: Task):
        """Push task result to all connected Pi clients."""
        message = {
            "type": "task_result",
            "kanban_id": task.kanban_id,
            "task_id": task.task_id,
            "status": task.status.value,
            "summary": task.result.get("summary") if task.result else None,
            "artifacts": [{"path": a, "type": "file"} for a in task.artifacts],
            "errors": [task.error] if task.error else [],
            "timestamp": datetime.now().timestamp(),
        }
        
        for client_id, ws in list(self.ws_connections.items()):
            try:
                ws.send(json.dumps(message))
            except Exception as e:
                logger.warning(f"Failed to push to {client_id}: {e}")
                self.unregister_ws_connection(client_id)
    
    # === RESULT HANDLERS ===
    
    def on_result(self, handler: callable):
        """Register a callback for when tasks complete."""
        self.result_handlers.append(handler)
    
    def _notify_result_handlers(self, task: Task):
        """Notify all registered handlers."""
        for handler in self.result_handlers:
            try:
                handler(task)
            except Exception as e:
                logger.error(f"Result handler error: {e}")
    
    # === STATUS ===
    
    def get_status(self) -> dict:
        """Get server status."""
        return {
            "running": True,
            "tasks_total": len(self.tasks),
            "tasks_pending": len(self.pending_queue),
            "tasks_processing": len(self.processing),
            "tasks_completed": len(self.completed),
            "connected_pis": len(self.ws_connections),
            "server_time": datetime.now().isoformat(),
        }


# ============================================================================
# HTTP API Server
# ============================================================================

from http.server import HTTPServer, BaseHTTPRequestHandler
import threading


class HermesAPIHandler(BaseHTTPRequestHandler):
    """HTTP handler for Hermes Core API."""
    
    def _send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def do_GET(self):
        path = self.path
        
        if path == "/health":
            self._send_json({"status": "ok", "server": "hermes-core"})
            
        elif path == "/status":
            self._send_json(self.server.hermes.get_status())
            
        elif path == "/tasks":
            # Get all tasks or filter by status
            status_filter = self._get_query_param("status")
            since = self._get_query_param("since")
            
            if since:
                results = self.server.hermes.get_results_since(float(since))
                self._send_json({"results": results, "count": len(results)})
            else:
                pending = self.server.hermes.get_pending_tasks()
                completed = self.server.hermes.get_completed_tasks(since_minutes=60)
                self._send_json({
                    "pending": [asdict(t) for t in pending],
                    "recently_completed": [asdict(t) for t in completed],
                })
            
        elif path.startswith("/task/"):
            kanban_id = path.split("/")[-1]
            task = self.server.hermes.get_task(kanban_id)
            if task:
                self._send_json(asdict(task))
            else:
                self._send_error(404, "Task not found")
        else:
            self.send_error(404, "Not found")
    
    def _get_query_param(self, name: str) -> Optional[str]:
        if "?" in self.path:
            query = self.path.split("?")[1]
            for param in query.split("&"):
                if param.startswith(f"{name}="):
                    return param.split("=")[1]
        return None
    
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"
        
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        
        path = self.path
        
        if path == "/delegate":
            # Pi delegates a task to Hermes
            title = data.get("title", "Untitled")
            description = data.get("description", "")
            priority = data.get("priority", "normal")
            context = data.get("context")
            
            task = self.server.hermes.create_task(title, description, priority, context)
            
            self._send_json({
                "success": True,
                "kanban_id": task.kanban_id,
                "status": task.status.value,
            })
            
        elif path == "/complete":
            # Mark task as complete (simulates work being done)
            kanban_id = data.get("kanban_id")
            result = data.get("result", {})
            artifacts = data.get("artifacts", [])
            
            success = self.server.hermes.complete_task(kanban_id, result, artifacts)
            
            self._send_json({"success": success})
            
        elif path == "/fail":
            kanban_id = data.get("kanban_id")
            error = data.get("error", "Unknown error")
            
            success = self.server.hermes.fail_task(kanban_id, error)
            
            self._send_json({"success": success})
            
        elif path == "/ping":
            # Heartbeat from Pi
            self._send_json({"pong": True, "server_time": datetime.now().isoformat()})
            
        else:
            self.send_error(404, "Not found")
    
    def log_message(self, format, *args):
        logger.debug(f"{self.address_string()} - {format % args}")


class HermesAPIServer(HTTPServer):
    """HTTP server with HermesCore attached."""
    
    def __init__(self, host: str, port: int, hermes: HermesCore):
        super().__init__((host, port), HermesAPIHandler)
        self.hermes = hermes


def run_server(host: str = "0.0.0.0", port: int = 8080):
    """Run the Hermes Core API server."""
    hermes = HermesCore(host, port)
    server = HermesAPIServer(host, port, hermes)
    
    logger.info(f"Hermes Core API server running on {host}:{port}")
    logger.info(f"  GET  /health - Server health")
    logger.info(f"  GET  /status - Server status")
    logger.info(f"  GET  /tasks - List all tasks")
    logger.info(f"  GET  /task/<kanban_id> - Get specific task")
    logger.info(f"  POST /delegate - Create new task (from Pi)")
    logger.info(f"  POST /complete - Mark task complete")
    logger.info(f"  POST /fail - Mark task failed")
    logger.info(f"  GET  /tasks?since=<timestamp> - Get results since timestamp")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped")
        server.shutdown()


# ============================================================================
# Cron Helper - For Hermes User to Poll
# ============================================================================

def poll_for_results(since_timestamp: float = None, callback: callable = None):
    """
    Poll Hermes for new results.
    
    Usage (for Hermes user cron job):
        from hermes_core import poll_for_results
        
        results = poll_for_results(since_timestamp=last_check)
        for result in results:
            print(f"Task {result['kanban_id']} completed: {result['result']}")
            # Trigger next step...
        
        last_check = time.time()  # Save for next poll
    """
    import urllib.request
    
    if since_timestamp:
        url = f"http://localhost:8080/tasks?since={since_timestamp}"
    else:
        url = "http://localhost:8080/tasks"
    
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read())
            
            if since_timestamp:
                results = data.get("results", [])
            else:
                # Get recently completed
                results = data.get("recently_completed", [])
            
            if callback:
                for result in results:
                    callback(result)
            
            return results
            
    except Exception as e:
        logger.error(f"Poll failed: {e}")
        return []


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hermes Core - Task Orchestration Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    
    args = parser.parse_args()
    run_server(args.host, args.port)
