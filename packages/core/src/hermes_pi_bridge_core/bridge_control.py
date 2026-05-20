"""
Bridge Control Panel - User Controls for Persistent Iteration

Provides a simple interface for you to:
1. Register callbacks to be notified when Pi completes tasks
2. Configure webhook endpoints for result notifications
3. Monitor the callback chain status
4. Manage iteration state

Usage:
    from bridge_control import BridgeControlPanel
    
    control = BridgeControlPanel()
    control.register_my_callback(my_callback_function)
    control.add_webhook("http://my-server.com/results")
    control.status()  # See what's configured
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class BridgeControlPanel:
    """
    Control panel for managing Hermes-Pi Bridge iteration.
    
    Provides user-facing controls for:
    - Callback registration (get notified when Pi finishes)
    - Webhook configuration (push results to external servers)
    - Status monitoring (see what's configured and working)
    - Iteration control (start/stop/configure)
    """

    def __init__(self):
        self._callbacks: list[Callable] = []
        self._webhook_endpoints: list[str] = []
        self._bridge = None
        self._initialized = False

    def _ensure_bridge(self):
        """Lazy initialization of bridge."""
        if not self._initialized:
            try:
                from hermes_pi_bridge_core.bridge import get_bridge
                self._bridge = get_bridge()
                self._initialized = True
                logger.info("Bridge initialized for control panel")
            except ImportError as e:
                logger.error(f"Could not import bridge: {e}")
                raise Exception("Bridge not available. Install hermes_pi_bridge_core.")

    def register_callback(self, callback: Callable) -> None:
        """
        Register a callback to be notified when Pi completes tasks.
        
        This is the KEY to persistent iteration:
        - Pi finishes → Your callback fires → You get result
        - No polling! Results are pushed to you.
        
        Args:
            callback: Function that receives (result: dict)
            
        Example:
            def on_pi_result(result):
                print(f"Pi finished: {result['task_id']}")
                # Evaluate result, decide next action
                
            control.register_callback(on_pi_result)
        """
        self._ensure_bridge()
        
        if callback not in self._callbacks:
            self._callbacks.append(callback)
            self._bridge.register_result_callback(callback)
            logger.info(f"Registered callback: {getattr(callback, '__name__', callback)}")
        else:
            logger.warning("Callback already registered")

    def unregister_callback(self, callback: Callable) -> bool:
        """Unregister a callback."""
        self._ensure_bridge()
        
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            self._bridge.unregister_result_callback(callback)
            logger.info("Unregistered callback")
            return True
        return False

    def add_webhook(self, endpoint: str) -> None:
        """
        Add a webhook endpoint to receive results.
        
        When Pi completes a task, an HTTP POST is sent to this endpoint
        with the result data.
        
        Args:
            endpoint: URL to receive POST notifications
            
        Example:
            control.add_webhook("http://my-server.com/api/pi-results")
        """
        self._ensure_bridge()
        
        if endpoint not in self._webhook_endpoints:
            self._webhook_endpoints.append(endpoint)
            self._bridge.add_webhook_endpoint(endpoint)
            logger.info(f"Added webhook: {endpoint}")
        else:
            logger.warning("Webhook already configured")

    def remove_webhook(self, endpoint: str) -> bool:
        """Remove a webhook endpoint."""
        self._ensure_bridge()
        
        if endpoint in self._webhook_endpoints:
            self._webhook_endpoints.remove(endpoint)
            self._bridge.remove_webhook_endpoint(endpoint)
            logger.info(f"Removed webhook: {endpoint}")
            return True
        return False

    def status(self) -> dict[str, Any]:
        """
        Get current status of the control panel.
        
        Returns:
            Dict with callbacks, webhooks, and bridge status
        """
        self._ensure_bridge()
        
        try:
            notification_stats = self._bridge.get_notification_stats()
        except AttributeError:
            notification_stats = {
                "registered_callbacks": len(self._callbacks),
                "webhook_endpoints": len(self._webhook_endpoints),
            }
        
        return {
            "callbacks_registered": len(self._callbacks),
            "callback_names": [getattr(cb, '__name__', str(cb)) for cb in self._callbacks],
            "webhooks_configured": len(self._webhook_endpoints),
            "webhook_endpoints": self._webhook_endpoints,
            "notification_stats": notification_stats,
            "bridge_initialized": self._initialized,
        }

    def clear(self) -> None:
        """Clear all callbacks and webhooks."""
        for callback in list(self._callbacks):
            self.unregister_callback(callback)
        
        for endpoint in list(self._webhook_endpoints):
            self.remove_webhook(endpoint)
        
        logger.info("Control panel cleared")

    def test_callback(self, test_data: dict = None) -> bool:
        """
        Test callback mechanism with test data.
        
        Args:
            test_data: Optional dict to send through callback chain
            
        Returns:
            True if callback fired successfully
        """
        self._ensure_bridge()
        
        test_data = test_data or {
            "task_id": "test-callback-001",
            "status": "success",
            "summary": "Test callback fired",
            "success": True,
        }
        
        # Simulate result receiving
        self._bridge.receive_result("pi", test_data)
        
        logger.info(f"Test callback sent: {test_data['task_id']}")
        return True


# =============================================================================
# Convenience Functions
# =============================================================================

_control_panel: Optional[BridgeControlPanel] = None


def get_control_panel() -> BridgeControlPanel:
    """Get singleton control panel."""
    global _control_panel
    if _control_panel is None:
        _control_panel = BridgeControlPanel()
    return _control_panel


def quick_register(callback: Callable) -> None:
    """Quick helper to register a callback."""
    panel = get_control_panel()
    panel.register_callback(callback)


def quick_webhook(endpoint: str) -> None:
    """Quick helper to add a webhook."""
    panel = get_control_panel()
    panel.add_webhook(endpoint)


# =============================================================================
# Example Usage
# =============================================================================

"""
Example: Full Persistent Iteration Setup

```python
from bridge_control import BridgeControlPanel, get_control_panel

# Initialize control panel
control = get_control_panel()

# 1. Register callback for when Pi finishes tasks
def on_pi_result(result):
    print(f"Task {result['task_id']} completed!")
    print(f"Status: {result['status']}")
    print(f"Summary: {result.get('summary', '')}")
    
    if result.get('artifacts'):
        print(f"Created: {len(result['artifacts'])} artifacts")
    
    # Now you can:
    # - Evaluate the result
    # - Decide next action
    # - Delegate new task to Pi
    
control.register_callback(on_pi_result)

# 2. Optionally, add webhook for external servers
# control.add_webhook("http://my-server.com/api/pi-results")

# 3. Check status
print(control.status())

# 4. Test the callback chain
control.test_callback()
```

This enables true persistent iteration without polling!
"""