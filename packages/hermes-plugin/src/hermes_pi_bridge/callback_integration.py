"""
Pi-Hermes Callback Integration

This module connects the Pi extension's callback system to Hermes's callback system,
enabling true end-to-end persistent iteration:

User → Pi: "write the API handler" → task_id
Pi → Hermes: HTTP POST delegation
Hermes → Pi: Push result via callback (no polling!)
Pi → User: Callback fires, user gets notified

The chain is:
1. User delegates to Pi (this agent)
2. Pi delegates to Hermes (HTTP POST to /delegate)
3. Hermes processes asynchronously
4. Hermes pushes result via /result endpoint
5. Pi receives result → triggers registered callbacks
6. User gets notified via callback (not polling!)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Result Handler Chain
# =============================================================================

@dataclass
class CallbackChain:
    """
    Manages the callback chain between Pi and Hermes.
    
    When Pi receives a result from Hermes, this chain ensures
    the result is pushed to all registered callbacks.
    """
    
    callbacks: list[Callable] = field(default_factory=list)
    
    def register(self, callback: Callable) -> None:
        """Register a callback."""
        if callback not in self.callbacks:
            self.callbacks.append(callback)
            logger.info(f"Registered callback: {getattr(callback, '__name__', callback)}")
    
    def unregister(self, callback: Callable) -> bool:
        """Unregister a callback."""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            return True
        return False
    
    def on_result(self, result: dict) -> None:
        """
        Invoke all callbacks when a result arrives.
        
        This is called when:
        1. Hermes pushes a result to /result endpoint
        2. Result is received by the Pi bridge server
        
        The result is then pushed to all registered callbacks.
        """
        logger.info(f"Pushing result to {len(self.callbacks)} callbacks: task_id={result.get('task_id')}")
        
        for callback in self.callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def clear(self) -> None:
        """Clear all callbacks."""
        self.callbacks.clear()


# =============================================================================
# Pi Bridge Result Handler
# =============================================================================

class PiResultHandler:
    """
    Handles results received from Hermes.
    
    This is the Pi-side of the callback chain:
    1. Receives HTTP POST from Hermes at /result
    2. Triggers internal callbacks
    3. Forwards to registered handlers
    
    Usage:
        handler = PiResultHandler()
        handler.register(my_callback)
        
        # When Hermes POSTs a result:
        handler.handle_result(result_data)
    """
    
    def __init__(self):
        self.chain = CallbackChain()
        self._webhook_endpoints: list[str] = []
        self._last_result: Optional[dict] = None
        self._result_history: list[dict] = []
        self._max_history = 100
        
        # Initialize bridge for webhook dispatch
        self._init_webhook_dispatcher()
    
    def _init_webhook_dispatcher(self):
        """Initialize webhook dispatcher for forwarding results."""
        try:
            from hermes_pi_bridge_core.notification import WebhookDispatcher
            self._dispatcher = WebhookDispatcher()
        except ImportError:
            self._dispatcher = None
    
    def register(self, callback: Callable) -> None:
        """Register a callback to receive results."""
        self.chain.register(callback)
    
    def unregister(self, callback: Callable) -> bool:
        """Unregister a callback."""
        return self.chain.unregister(callback)
    
    def add_webhook(self, endpoint: str) -> None:
        """Add webhook endpoint to forward results."""
        if self._dispatcher and endpoint not in self._webhook_endpoints:
            self._webhook_endpoints.append(endpoint)
            self._dispatcher.add_channel(endpoint)
            logger.info(f"Added webhook: {endpoint}")
    
    def handle_result(self, result: dict) -> None:
        """
        Handle a result received from Hermes.
        
        This is the main entry point:
        1. Stores result in history
        2. Triggers all registered callbacks (PUSH!)
        3. Forwards to webhooks if configured
        
        Args:
            result: Result dict from Hermes
        """
        # Store in history
        self._last_result = result
        self._result_history.append({
            **result,
            "received_at": time.time(),
        })
        
        # Trim history
        if len(self._result_history) > self._max_history:
            self._result_history = self._result_history[-self._max_history:]
        
        # Trigger callbacks (PUSH - no polling!)
        self.chain.on_result(result)
        
        # Forward to webhooks
        if self._dispatcher and self._webhook_endpoints:
            try:
                from hermes_pi_bridge_core.notification import NotificationPayload
                payload = NotificationPayload.from_result(result, source="hermes")
                self._dispatcher.dispatch(payload)
            except Exception as e:
                logger.error(f"Webhook dispatch failed: {e}")
        
        logger.info(f"Result handled: {result.get('task_id')} -> {result.get('status')}")
    
    def get_last_result(self) -> Optional[dict]:
        """Get the most recent result."""
        return self._last_result
    
    def get_history(self, limit: int = 10) -> list[dict]:
        """Get recent results."""
        return self._result_history[-limit:]
    
    def get_stats(self) -> dict:
        """Get handler statistics."""
        return {
            "callbacks_registered": len(self.chain.callbacks),
            "webhooks_configured": len(self._webhook_endpoints),
            "results_received": len(self._result_history),
            "last_result": self._last_result.get("task_id") if self._last_result else None,
        }


# =============================================================================
# Integration with Hermes Bridge Server
# =============================================================================

def setup_pi_callback_integration(server_module: Any = None) -> PiResultHandler:
    """
    Set up callback integration for Pi bridge server.
    
    This wires the server's /result endpoint to the callback chain,
    so results from Hermes automatically trigger callbacks.
    
    Args:
        server_module: Optional server module to patch
        
    Returns:
        PiResultHandler instance
    """
    handler = PiResultHandler()
    
    # Try to patch the server if provided
    if server_module and hasattr(server_module, 'emit_task_completed'):
        original_emit = server_module.emit_task_completed
        
        async def patched_emit(task):
            # Call original
            await original_emit(task)
            
            # Also trigger our handler
            if hasattr(task, 'result') and task.result:
                result = {
                    "task_id": task.task_id,
                    "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                    "summary": task.result.get("summary", ""),
                    "artifacts": task.result.get("artifacts", []),
                    "errors": task.result.get("errors", []),
                    "success": task.status.value in ("success", "partial") if hasattr(task.status, 'value') else True,
                }
                handler.handle_result(result)
        
        server_module.emit_task_completed = patched_emit
    
    logger.info("Pi callback integration configured")
    return handler


# =============================================================================
# Async Callback Support
# =============================================================================

class AsyncCallbackHandler:
    """
    Async-aware callback handler for async environments.
    
    Use this when you need callbacks that can await async operations.
    """
    
    def __init__(self):
        self._callbacks: list[Callable] = []
    
    def register(self, callback: Callable) -> None:
        """Register a callback."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)
    
    async def trigger(self, result: dict) -> None:
        """Trigger all callbacks asynchronously."""
        import asyncio
        
        tasks = []
        for callback in self._callbacks:
            try:
                # Check if callback is async
                if asyncio.iscoroutinefunction(callback):
                    tasks.append(callback(result))
                else:
                    # Run sync callback in thread pool
                    loop = asyncio.get_event_loop()
                    tasks.append(loop.run_in_executor(None, lambda: callback(result)))
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
        # Wait for all callbacks (but don't block on errors)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# =============================================================================
# Singleton
# =============================================================================

_pi_result_handler: Optional[PiResultHandler] = None


def get_pi_result_handler() -> PiResultHandler:
    """Get singleton Pi result handler."""
    global _pi_result_handler
    if _pi_result_handler is None:
        _pi_result_handler = PiResultHandler()
    return _pi_result_handler


def reset_pi_handler() -> None:
    """Reset singleton (for testing)."""
    global _pi_result_handler
    _pi_result_handler = None