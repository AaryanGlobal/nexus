"""
Hermes-Pi Bridge Core
====================

Shared types and protocol definitions for Hermes-Pi Bridge.
This package is used by both Hermes plugin and standalone tools.

Callback System (Key Feature - enables PUSH-based iteration):
    The callback system eliminates polling by pushing results:
    - Pi finishes task → Hermes receives result
    - Hermes triggers registered callbacks  
    - User gets notified automatically (no polling!)
    
    Usage:
        from hermes_pi_bridge_core import get_bridge
        
        bridge = get_bridge()
        bridge.register_result_callback(my_callback)
        # Now my_callback fires when Pi completes tasks
"""

from .types import (
    AgentStatus,
    AgentType,
    ErrorCode,
    Priority,
    ProtocolVersion,
    TaskContext,
    TaskDelegateRequest,
    TaskResult,
    TaskStatus,
)

# Callback and notification system (optional - graceful fallback)
try:
    from .callback import (
        CallbackRegistry,
        CallbackHandler,
        CallbackEvent,
        ResultCallback,
        TaskCompletionCallback,
        NotificationChannel,
        NotificationPayload,
        get_callback_registry,
        get_callback_handler,
        reset_callbacks,
    )
    from .notification import (
        NotificationServer,
        WebhookDispatcher,
        BridgeResultHandler,
        get_webhook_dispatcher,
        get_notification_server,
        get_result_handler,
    )
    from .bridge_control import (
        BridgeControlPanel,
        get_control_panel,
        quick_register,
        quick_webhook,
    )
    from .control_panel import start_web_ui
    CALLBACK_SYSTEM_AVAILABLE = True
except ImportError:
    # Graceful fallback if callback system not available
    CALLBACK_SYSTEM_AVAILABLE = False

__version__ = "1.0.0"
__all__ = [
    # Types
    "AgentType",
    "AgentStatus",
    "ErrorCode",
    "Priority",
    "ProtocolVersion",
    "TaskContext",
    "TaskDelegateRequest",
    "TaskResult",
    "TaskStatus",
    # Callback system
    "CallbackRegistry",
    "CallbackHandler",
    "CallbackEvent",
    "ResultCallback",
    "TaskCompletionCallback",
    "NotificationChannel",
    "NotificationPayload",
    "get_callback_registry",
    "get_callback_handler",
    "reset_callbacks",
    # Notification system
    "NotificationServer",
    "WebhookDispatcher",
    "BridgeResultHandler",
    "get_webhook_dispatcher",
    "get_notification_server",
    "get_result_handler",
    # Control panel
    "BridgeControlPanel",
    "get_control_panel",
    "quick_register",
    "quick_webhook",
    "start_web_ui",
    "CALLBACK_SYSTEM_AVAILABLE",
]