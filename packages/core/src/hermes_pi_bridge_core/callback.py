"""
Callback System - Enables Push-Based Notification Chain

This module bridges the gap between:
- Pi finishing a task
- Hermes receiving the result
- You being notified (no polling)

The callback chain:
1. Pi completes task → POST to /api/v1/task.result
2. Hermes server → emit_task_completed()
3. emit_task_completed → CallbackRegistry.emit()
4. CallbackRegistry → Registered callbacks fire
5. Result pushed to you (via webhook, SSE, or internal callback)

This enables true persistent iteration without polling.
"""

from __future__ import annotations

import logging
import threading
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Callback Events
# =============================================================================

class CallbackEvent(Enum):
    """Events that can trigger callbacks."""
    TASK_DELEGATED = "task_delegated"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_PROGRESS = "task_progress"
    AGENT_CONNECTED = "agent_connected"
    AGENT_DISCONNECTED = "agent_disconnected"
    ERROR = "error"
    RESULT_RECEIVED = "result_received"


# =============================================================================
# Callback Registry
# =============================================================================

class CallbackRegistry:
    """
    Central registry for callback handlers.
    
    Manages registration and dispatch of callbacks for different events.
    Thread-safe for concurrent access.
    """

    def __init__(self):
        self._handlers: dict[CallbackEvent, list[Callable]] = {}
        self._lock = threading.RLock()
        self._event_history: list[dict] = []
        self._max_history = 100

    def register(
        self,
        event: CallbackEvent,
        callback: Callable,
        priority: int = 0,
    ) -> None:
        """
        Register a callback for an event.
        
        Args:
            event: Event to listen for
            callback: Function to call when event fires
            priority: Higher priority callbacks fire first (default: 0)
        """
        with self._lock:
            if event not in self._handlers:
                self._handlers[event] = []
            
            # Add with priority info
            self._handlers[event].append((priority, callback))
            # Sort by priority (higher first)
            self._handlers[event].sort(key=lambda x: -x[0])
            
            logger.debug(f"Registered callback for {event.value}")

    def unregister(
        self,
        event: CallbackEvent,
        callback: Callable,
    ) -> bool:
        """
        Unregister a callback.
        
        Args:
            event: Event to stop listening for
            callback: Callback to remove
            
        Returns:
            True if callback was found and removed
        """
        with self._lock:
            if event not in self._handlers:
                return False
            
            # Find and remove callback
            for i, (priority, cb) in enumerate(self._handlers[event]):
                if cb == callback:
                    self._handlers[event].pop(i)
                    logger.debug(f"Unregistered callback for {event.value}")
                    return True
            
            return False

    def emit(
        self,
        event: CallbackEvent,
        data: dict[str, Any],
    ) -> None:
        """
        Emit an event to all registered callbacks.
        
        Args:
            event: Event that occurred
            data: Event data to pass to callbacks
        """
        # Record in history
        self._record_event(event, data)
        
        with self._lock:
            handlers = list(self._handlers.get(event, []))
        
        # Call each handler (outside lock)
        for priority, callback in handlers:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error for {event.value}: {e}")
                # Continue to next callback even if one fails

    def clear(self, event: Optional[CallbackEvent] = None) -> None:
        """Clear callbacks for event, or all events if None."""
        with self._lock:
            if event:
                self._handlers[event] = []
            else:
                self._handlers.clear()

    def _record_event(self, event: CallbackEvent, data: dict) -> None:
        """Record event in history for debugging."""
        with self._lock:
            self._event_history.append({
                "event": event.value,
                "data": data,
                "timestamp": datetime.now().isoformat(),
            })
            # Keep history bounded
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history:]

    def get_history(self, limit: int = 10) -> list[dict]:
        """Get recent event history."""
        with self._lock:
            return list(self._event_history[-limit:])


# =============================================================================
# Callback Handler (High-Level Interface)
# =============================================================================

class CallbackHandler:
    """
    High-level interface for callback management.
    
    Provides simple methods for common callback patterns.
    """

    def __init__(self):
        self.registry = CallbackRegistry()
        self._result_callbacks: list[Callable] = []
        self._delegation_callbacks: list[Callable] = []
        self._error_callbacks: list[Callable] = []
        self._lock = threading.RLock()

    def add_result_callback(self, callback: Callable) -> None:
        """Add callback for task results."""
        with self._lock:
            self._result_callbacks.append(callback)
        self.registry.register(CallbackEvent.RESULT_RECEIVED, callback)

    def remove_result_callback(self, callback: Callable) -> bool:
        """Remove result callback."""
        with self._lock:
            if callback in self._result_callbacks:
                self._result_callbacks.remove(callback)
                return self.registry.unregister(CallbackEvent.RESULT_RECEIVED, callback)
        return False

    def add_delegation_callback(self, callback: Callable) -> None:
        """Add callback for task delegations."""
        with self._lock:
            self._delegation_callbacks.append(callback)
        self.registry.register(CallbackEvent.TASK_DELEGATED, callback)

    def add_error_callback(self, callback: Callable) -> None:
        """Add callback for errors."""
        with self._lock:
            self._error_callbacks.append(callback)
        self.registry.register(CallbackEvent.ERROR, callback)

    def trigger_result(self, result: dict[str, Any]) -> None:
        """Trigger result callbacks."""
        self.registry.emit(CallbackEvent.RESULT_RECEIVED, result)
        
        # Also emit specific event based on status
        if result.get("success"):
            self.registry.emit(CallbackEvent.TASK_COMPLETED, result)
        else:
            self.registry.emit(CallbackEvent.TASK_FAILED, result)

    def trigger_delegation(self, delegation: dict[str, Any]) -> None:
        """Trigger delegation callbacks."""
        self.registry.emit(CallbackEvent.TASK_DELEGATED, delegation)

    def trigger_error(self, error: dict[str, Any]) -> None:
        """Trigger error callbacks."""
        self.registry.emit(CallbackEvent.ERROR, error)

    def get_stats(self) -> dict[str, Any]:
        """Get callback statistics."""
        with self._lock:
            return {
                "result_callbacks": len(self._result_callbacks),
                "delegation_callbacks": len(self._delegation_callbacks),
                "error_callbacks": len(self._error_callbacks),
                "event_history_size": len(self.registry._event_history),
            }


# =============================================================================
# Notification Channel
# =============================================================================

@dataclass
class NotificationChannel:
    """
    Configuration for a notification delivery channel.
    
    Can be webhook (HTTP POST), SSE (Server-Sent Events), or internal callback.
    """
    
    channel_type: str = "webhook"  # webhook, sse, callback
    endpoint: str = ""
    
    # Delivery settings
    enabled: bool = True
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    timeout_seconds: float = 30.0
    
    # Filtering
    notify_on_success: bool = True
    notify_on_failure: bool = True
    notify_on_progress: bool = False
    
    # Authentication
    auth_token: Optional[str] = None
    
    # Metadata
    name: str = ""
    description: str = ""

    @classmethod
    def configure_webhook(
        cls,
        endpoint: str,
        retry_attempts: int = 3,
        timeout_seconds: float = 30.0,
        auth_token: Optional[str] = None,
    ) -> "NotificationChannel":
        """Create webhook channel configuration."""
        return cls(
            channel_type="webhook",
            endpoint=endpoint,
            retry_attempts=retry_attempts,
            timeout_seconds=timeout_seconds,
            auth_token=auth_token,
        )

    @classmethod
    def configure_callback(
        cls,
        callback: Callable,
    ) -> "NotificationChannel":
        """Create internal callback channel."""
        return cls(
            channel_type="callback",
            endpoint=str(id(callback)),  # Use callback id as identifier
            name=f"callback_{id(callback)}",
        )


# =============================================================================
# Result Callback (Typed Callback)
# =============================================================================

@dataclass
class ResultCallback:
    """
    A callback for task results with typed data.
    
    Provides type-safe callback handling.
    """
    
    callback: Callable
    event_types: list[CallbackEvent] = field(default_factory=list)
    filter_fn: Optional[Callable[[dict], bool]] = None
    priority: int = 0
    
    def should_fire(self, event: CallbackEvent, data: dict) -> bool:
        """Check if callback should fire for this event/data."""
        if self.event_types and event not in self.event_types:
            return False
        
        if self.filter_fn and not self.filter_fn(data):
            return False
        
        return True

    def invoke(self, data: dict) -> Any:
        """Invoke the callback."""
        return self.callback(data)


# =============================================================================
# Task Completion Callback
# =============================================================================

@dataclass 
class TaskCompletionCallback:
    """
    Specialized callback for task completion events.
    
    Provides convenient access to task result data.
    """
    
    on_success: Optional[Callable] = None
    on_failure: Optional[Callable] = None
    on_progress: Optional[Callable] = None
    
    def invoke(self, result: dict[str, Any]) -> None:
        """Invoke appropriate callback based on result status."""
        success = result.get("success", False)
        
        if success and self.on_success:
            self.on_success(result)
        elif not success and self.on_failure:
            self.on_failure(result)
        elif self.on_progress:
            self.on_progress(result)


# =============================================================================
# Notification Payload
# =============================================================================

@dataclass
class NotificationPayload:
    """
    Standard payload for notifications.
    
    Contains all information about a task result.
    """
    
    task_id: str
    status: str
    summary: str = ""
    artifacts: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    
    # Context
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source_agent: str = ""  # hermes or pi
    kanban_id: Optional[str] = None
    
    # Metadata
    duration_seconds: Optional[float] = None
    priority: str = "normal"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "status": self.status,
            "summary": self.summary,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "timestamp": self.timestamp,
            "source_agent": self.source_agent,
            "kanban_id": self.kanban_id,
            "duration_seconds": self.duration_seconds,
            "priority": self.priority,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_result(cls, result: dict, source: str = "pi") -> "NotificationPayload":
        """Create payload from result dict."""
        return cls(
            task_id=result.get("task_id", result.get("pi_task_id", "unknown")),
            status="success" if result.get("success") else "failed",
            summary=result.get("summary", result.get("summary", "")),
            artifacts=result.get("artifacts", []),
            errors=result.get("errors", []),
            source_agent=source,
            duration_seconds=result.get("duration_seconds"),
            priority=result.get("priority", "normal"),
        )


# =============================================================================
# Singleton Registry
# =============================================================================

_callback_registry: Optional[CallbackRegistry] = None
_callback_handler: Optional[CallbackHandler] = None


def get_callback_registry() -> CallbackRegistry:
    """Get global callback registry."""
    global _callback_registry
    if _callback_registry is None:
        _callback_registry = CallbackRegistry()
    return _callback_registry


def get_callback_handler() -> CallbackHandler:
    """Get global callback handler."""
    global _callback_handler
    if _callback_handler is None:
        _callback_handler = CallbackHandler()
    return _callback_handler


def reset_callbacks() -> None:
    """Reset global callback state (for testing)."""
    global _callback_registry, _callback_handler
    _callback_registry = None
    _callback_handler = None