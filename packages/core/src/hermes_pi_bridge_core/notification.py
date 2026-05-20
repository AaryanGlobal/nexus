"""
Notification System - Push Results to Subscribers

Enables push-based notifications via:
1. WebhookDispatcher - HTTP POST to configured endpoints
2. NotificationServer - Local server for receiving notifications
3. SSE support (future) - Server-Sent Events for real-time updates

This eliminates polling by pushing results when tasks complete.
"""

from __future__ import annotations

import logging
import threading
import json
import time
from datetime import datetime
from typing import Any, Optional, Callable
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from .callback import (
    CallbackEvent,
    NotificationChannel,
    NotificationPayload,
    get_callback_registry,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Webhook Dispatcher
# =============================================================================

class WebhookDispatcher:
    """
    Dispatches notifications via HTTP webhooks.
    
    When a task completes, sends POST to configured webhook endpoints.
    Supports retry logic and timeout handling.
    """

    def __init__(self, base_url: str = ""):
        self.base_url = base_url
        self.channels: list[str] = []
        self._lock = threading.RLock()
        
        # Statistics
        self.total_sent = 0
        self.total_failed = 0
        self.last_send_time: Optional[datetime] = None

    def add_channel(self, endpoint: str) -> None:
        """Add a webhook endpoint."""
        with self._lock:
            if endpoint not in self.channels:
                self.channels.append(endpoint)
                logger.info(f"Added webhook channel: {endpoint}")

    def remove_channel(self, endpoint: str) -> bool:
        """Remove a webhook endpoint."""
        with self._lock:
            if endpoint in self.channels:
                self.channels.remove(endpoint)
                logger.info(f"Removed webhook channel: {endpoint}")
                return True
            return False

    def build_payload(
        self,
        task_id: str,
        status: str,
        summary: str = "",
        artifacts: list[dict] = None,
        errors: list[str] = None,
        source: str = "hermes",
        metadata: dict = None,
    ) -> NotificationPayload:
        """Build notification payload."""
        return NotificationPayload(
            task_id=task_id,
            status=status,
            summary=summary,
            artifacts=artifacts or [],
            errors=errors or [],
            timestamp=datetime.now().isoformat(),
            source_agent=source,
            duration_seconds=None,
        )

    def dispatch(
        self,
        payload: NotificationPayload,
        endpoint: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Dispatch notification to webhook(s).
        
        Args:
            payload: Notification payload to send
            endpoint: Specific endpoint, or None for all
            
        Returns:
            Dict with success status and any errors
        """
        endpoints = [endpoint] if endpoint else list(self.channels)
        
        results = {
            "total": len(endpoints),
            "sent": 0,
            "failed": 0,
            "errors": [],
        }
        
        for ep in endpoints:
            try:
                self._send_webhook(ep, payload)
                results["sent"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"{ep}: {str(e)}")
                logger.error(f"Webhook dispatch failed to {ep}: {e}")
        
        self.total_sent += results["sent"]
        self.total_failed += results["failed"]
        self.last_send_time = datetime.now()
        
        return results

    def _send_webhook(
        self,
        endpoint: str,
        payload: NotificationPayload,
        timeout: float = 30.0,
        retry_attempts: int = 3,
    ) -> bool:
        """
        Send webhook to endpoint with retry logic.
        
        Args:
            endpoint: Webhook URL
            payload: Notification payload
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts
            
        Returns:
            True if successful, raises exception on failure
        """
        last_error = None
        
        for attempt in range(retry_attempts):
            try:
                data = json.dumps(payload.to_dict()).encode("utf-8")
                
                req = Request(
                    endpoint,
                    data=data,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Hermes-Pi-Bridge/1.0",
                    },
                )
                
                response = urlopen(req, timeout=timeout)
                response.read()  # Consume response
                
                logger.info(f"Webhook sent successfully to {endpoint}")
                return True
                
            except HTTPError as e:
                last_error = f"HTTP {e.code}: {e.reason}"
                logger.warning(f"Webhook attempt {attempt + 1} failed: {last_error}")
                
            except URLError as e:
                last_error = f"URL error: {e.reason}"
                logger.warning(f"Webhook attempt {attempt + 1} failed: {last_error}")
                
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                logger.warning(f"Webhook attempt {attempt + 1} failed: {last_error}")
            
            # Wait before retry (exponential backoff)
            if attempt < retry_attempts - 1:
                wait_time = min(30, 2 ** attempt)
                time.sleep(wait_time)
        
        # All retries exhausted
        raise Exception(f"Webhook failed after {retry_attempts} attempts: {last_error}")

    def dispatch_result(self, result: dict) -> dict[str, Any]:
        """
        Convenience method to dispatch a result dict.
        
        Args:
            result: Result dict from task completion
            
        Returns:
            Dispatch results
        """
        # Check if result should trigger notification
        if not result.get("success", False):
            # Check failure notification setting
            channel_config = NotificationChannel()
            if not channel_config.notify_on_failure:
                return {"skipped": True, "reason": "failure notifications disabled"}
        else:
            channel_config = NotificationChannel()
            if not channel_config.notify_on_success:
                return {"skipped": True, "reason": "success notifications disabled"}
        
        # Build payload
        payload = NotificationPayload.from_result(result, source="pi")
        
        # Dispatch
        return self.dispatch(payload)

    def get_stats(self) -> dict[str, Any]:
        """Get dispatcher statistics."""
        with self._lock:
            return {
                "total_channels": len(self.channels),
                "total_sent": self.total_sent,
                "total_failed": self.total_failed,
                "last_send_time": self.last_send_time.isoformat() if self.last_send_time else None,
                "success_rate": (
                    self.total_sent / (self.total_sent + self.total_failed)
                    if (self.total_sent + self.total_failed) > 0
                    else 1.0
                ),
            }


# =============================================================================
# Notification Server
# =============================================================================

class NotificationServer:
    """
    Local server for receiving notifications.
    
    Provides HTTP endpoints for:
    - /callback - Generic callback receiver
    - /result - Task result receiver
    - /health - Health check
    
    Used internally by the bridge to receive notifications
    and forward them via registered callbacks.
    """

    def __init__(
        self,
        port: int = 9000,
        host: str = "0.0.0.0",
    ):
        self.port = port
        self.host = host
        self.running = False
        
        # Routes
        self._routes: dict[str, Callable] = {}
        self._lock = threading.RLock()
        
        # Statistics
        self.requests_received = 0
        self.requests_handled = 0
        
        # Server instance
        self._server = None
        self._thread: Optional[threading.Thread] = None

    def register(self, path: str, handler: Callable) -> None:
        """Register a callback handler for a path."""
        with self._lock:
            self._routes[path] = handler
            logger.info(f"Registered notification route: {path}")

    def unregister(self, path: str) -> bool:
        """Unregister a route."""
        with self._lock:
            if path in self._routes:
                del self._routes[path]
                return True
            return False

    def start(self) -> bool:
        """Start the notification server."""
        if self.running:
            logger.warning("Notification server already running")
            return False
        
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        self.running = True
        
        logger.info(f"Notification server starting on {self.host}:{self.port}")
        return True

    def stop(self) -> bool:
        """Stop the notification server."""
        self.running = False
        
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
        
        logger.info("Notification server stopped")
        return True

    def _run_server(self) -> None:
        """Run the HTTP server (blocking)."""
        try:
            from http.server import HTTPServer, BaseHTTPRequestHandler
            
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    self._handle_request("GET")
                    
                def do_POST(self):
                    self._handle_request("POST")
                
                def _handle_request(self, method: str):
                    server.requests_received += 1
                    
                    # Get handler
                    handler = server._routes.get(self.path)
                    
                    if not handler:
                        self.send_error(404, "Route not found")
                        return
                    
                    # Read body for POST
                    body = b""
                    if method == "POST":
                        content_length = int(self.headers.get("Content-Length", 0))
                        if content_length > 0:
                            body = self.rfile.read(content_length)
                    
                    # Parse body
                    data = {}
                    if body:
                        try:
                            data = json.loads(body.decode("utf-8"))
                        except json.JSONDecodeError:
                            pass
                    
                    # Call handler
                    try:
                        result = handler(data)
                        server.requests_handled += 1
                        
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(json.dumps(result).encode())
                        
                    except Exception as e:
                        self.send_response(500)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": str(e)}).encode())
                
                def log_message(self, format, *args):
                    logger.info(f"{self.address_string()} - {format % args}")
            
            # Store reference for handler
            server = self
            self._server = HTTPServer((self.host, self.port), Handler)
            self._server.serve_forever()
            
        except Exception as e:
            logger.error(f"Notification server error: {e}")
            self.running = False

    def handle_callback(self, data: dict) -> dict:
        """Default callback handler."""
        logger.info(f"Received callback: {data}")
        
        # Emit to callback registry
        registry = get_callback_registry()
        registry.emit(CallbackEvent.RESULT_RECEIVED, data)
        
        return {"received": True, "processed": True}

    def handle_result(self, data: dict) -> dict:
        """Result handler - processes task results."""
        task_id = data.get("task_id")
        
        logger.info(f"Received result for task {task_id}")
        
        # Emit completion event
        registry = get_callback_registry()
        registry.emit(CallbackEvent.TASK_COMPLETED, data)
        
        return {"received": True, "task_id": task_id}

    def get_stats(self) -> dict[str, Any]:
        """Get server statistics."""
        return {
            "running": self.running,
            "host": self.host,
            "port": self.port,
            "routes": list(self._routes.keys()),
            "requests_received": self.requests_received,
            "requests_handled": self.requests_handled,
        }


# =============================================================================
# Bridge Result Handler (Wires Everything)
# =============================================================================

class BridgeResultHandler:
    """
    Handles bridge results and wires to callback system.
    
    This is the key integration point that:
    1. Receives results from Pi (via Hermes server)
    2. Triggers registered callbacks
    3. Dispatches webhook notifications
    4. Updates Kanban
    """

    def __init__(self):
        self.callback_handler = get_callback_registry()
        self.webhook_dispatcher = WebhookDispatcher()
        self.notification_server = NotificationServer()
        
        # Auto-wire: results trigger callbacks
        self._setup_default_handlers()

    def _setup_default_handlers(self) -> None:
        """Set up default callback handlers."""
        # Register default handler for results
        def on_result(result: dict):
            # Dispatch webhook if configured
            if self.webhook_dispatcher.channels:
                self.webhook_dispatcher.dispatch_result(result)
        
        self.callback_handler.register(CallbackEvent.RESULT_RECEIVED, on_result)

    def on_result_received(self, result: dict) -> None:
        """
        Handle result received from Pi.
        
        This is the main entry point for result handling.
        Triggers callback chain and webhook dispatch.
        """
        logger.info(f"Handling result for task {result.get('task_id')}")
        
        # Emit to callback registry
        self.callback_handler.emit(CallbackEvent.RESULT_RECEIVED, result)
        
        # Also emit specific completion/failure event
        if result.get("success"):
            self.callback_handler.emit(CallbackEvent.TASK_COMPLETED, result)
        else:
            self.callback_handler.emit(CallbackEvent.TASK_FAILED, result)

    def add_webhook_endpoint(self, endpoint: str) -> None:
        """Add webhook endpoint for result notifications."""
        self.webhook_dispatcher.add_channel(endpoint)

    def remove_webhook_endpoint(self, endpoint: str) -> bool:
        """Remove webhook endpoint."""
        return self.webhook_dispatcher.remove_channel(endpoint)

    def register_result_callback(self, callback: Callable) -> None:
        """Register callback to be called when results arrive."""
        self.callback_handler.register(CallbackEvent.RESULT_RECEIVED, callback)

    def get_stats(self) -> dict[str, Any]:
        """Get handler statistics."""
        return {
            "callbacks": {
                "total": len(self.callback_handler._handlers),
                "result_listeners": len([
                    cb for cb in self.callback_handler._handlers.get(CallbackEvent.RESULT_RECEIVED, [])
                ]),
            },
            "webhooks": self.webhook_dispatcher.get_stats(),
            "server": self.notification_server.get_stats(),
        }


# =============================================================================
# Singleton Instances
# =============================================================================

_webhook_dispatcher: Optional[WebhookDispatcher] = None
_notification_server: Optional[NotificationServer] = None
_result_handler: Optional[BridgeResultHandler] = None


def get_webhook_dispatcher() -> WebhookDispatcher:
    """Get global webhook dispatcher."""
    global _webhook_dispatcher
    if _webhook_dispatcher is None:
        _webhook_dispatcher = WebhookDispatcher()
    return _webhook_dispatcher


def get_notification_server(port: int = 9000) -> NotificationServer:
    """Get global notification server."""
    global _notification_server
    if _notification_server is None:
        _notification_server = NotificationServer(port=port)
    return _notification_server


def get_result_handler() -> BridgeResultHandler:
    """Get global result handler."""
    global _result_handler
    if _result_handler is None:
        _result_handler = BridgeResultHandler()
    return _result_handler