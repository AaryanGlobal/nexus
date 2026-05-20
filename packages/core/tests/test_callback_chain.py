"""
Test: End-to-End Callback Chain for Hermes-Pi Bridge

Tests the notification chain:
1. Pi delegates to Hermes → task created
2. Hermes processes → callback to Pi
3. Pi finishes → reports result back to Hermes
4. Hermes → notifies Hermes user (me) via callback

This enables true end-to-end iterative production.
"""
import pytest
import json
import threading
import time
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, asdict

# Add package to path
import sys
from pathlib import Path

# Add nexus root to path for hermes_core
nexus_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(nexus_root))
sys.path.insert(0, str(nexus_root / "packages" / "core" / "src"))


class TestCallbackChain:
    """Test the complete callback notification chain."""
    
    def test_hermes_creates_task_and_pi_receives_it(self):
        """Pi delegates task to Hermes, receives confirmation."""
        from hermes_pi_bridge_core.bridge import AgentBridge, AgentType
        
        bridge = AgentBridge(pi_url="http://localhost:8645")
        
        # Test that delegate_task adds to message history
        task_id = bridge.delegate_task(AgentType.HERMES, {
            "title": "Test task",
            "description": "Test description"
        })
        
        # Task should be added to history
        assert task_id is not None
        assert len(bridge.message_history) > 0
        
        # Message should be a task delegation
        last_msg = bridge.message_history[-1]
        assert "task_delegate" in str(last_msg.type)
    
    def test_hermes_core_callback_registration(self):
        """Hermes Core allows registering callback URLs."""
        from hermes_core import HermesCore
        
        hermes = HermesCore(host="127.0.0.1", port=18080)
        
        # Register callback
        hermes.register_callback("http://localhost:9999/callback")
        
        assert "http://localhost:9999/callback" in hermes.callback_urls
        
        # Unregister callback
        hermes.unregister_callback("http://localhost:9999/callback")
        
        assert "http://localhost:9999/callback" not in hermes.callback_urls
    
    def test_hermes_core_invokes_callback_on_task_complete(self):
        """When task completes, Hermes Core invokes registered callbacks."""
        from hermes_core import HermesCore
        
        hermes = HermesCore(host="127.0.0.1", port=18081)
        
        # Track callback invocations
        callback_invocations = []
        
        def test_callback(url: str, payload: dict):
            callback_invocations.append(payload)
        
        # Patch _send_callback to intercept
        original_send = hermes._send_callback
        hermes._send_callback = test_callback
        
        # Register callback
        hermes.register_callback("http://test/callback")
        
        # Create and complete task
        task = hermes.create_task("Test", "Test task")
        hermes.complete_task(task.kanban_id, {"summary": "Done"}, ["file.txt"])
        
        assert len(callback_invocations) == 1
        assert callback_invocations[0]["kanban_id"] == task.kanban_id
        assert callback_invocations[0]["result"]["summary"] == "Done"
    
    def test_pi_reports_result_to_hermes(self):
        """Pi reports result back to Hermes Core."""
        from hermes_core import HermesCore
        
        hermes = HermesCore(host="127.0.0.1", port=18082)
        
        # Create a task first (simulating Hermes receiving delegate from Pi)
        task = hermes.create_task("Pi Task", "Pi should complete this")
        
        # Simulate Pi calling reportResult
        # This would be done via HTTP POST to /result
        # For now, just verify task exists
        assert hermes.get_task(task.kanban_id) is not None
        
        # Now Pi completes it via the HTTP API (would be tested via handler)
        result = {"summary": "Task completed by Pi", "output": "output.txt"}
        success = hermes.complete_task(task.kanban_id, result)
        
        assert success is True
        assert hermes.get_task(task.kanban_id).status.value == "completed"
    
    def test_result_push_to_connected_pi_client(self):
        """Results are pushed via WebSocket to connected Pi clients."""
        from hermes_core import HermesCore
        
        hermes = HermesCore(host="127.0.0.1", port=18083)
        
        # Track pushed messages
        pushed_messages = []
        
        mock_ws = MagicMock()
        def track_send(msg):
            pushed_messages.append(json.loads(msg))
        mock_ws.send = track_send
        
        # Register mock WebSocket client
        hermes.register_ws_connection("pi-client-1", mock_ws)
        
        # Complete task
        task = hermes.create_task("Push Test", "Should push result")
        hermes.complete_task(task.kanban_id, {"summary": "Pushed!"})
        
        assert len(pushed_messages) == 1
        assert pushed_messages[0]["type"] == "task_result"
        assert pushed_messages[0]["kanban_id"] == task.kanban_id
    
    def test_callback_fails_gracefully(self):
        """Callback failures don't crash the server."""
        from hermes_core import HermesCore
        
        hermes = HermesCore(host="127.0.0.1", port=18084)
        
        # Register a callback that will fail
        hermes.register_callback("http://localhost:99999/fail")
        
        # Create and complete task - should not raise
        task = hermes.create_task("Fail Test", "Task")
        hermes.complete_task(task.kanban_id, {"summary": "Done"})
        
        # Task should still be marked complete
        assert hermes.get_task(task.kanban_id).status.value == "completed"


class TestEndToEndFlow:
    """Test the complete end-to-end flow."""
    
    def test_full_delegate_complete_flow(self):
        """Complete flow: Pi delegates → Hermes processes → notifies → Pi gets result."""
        from hermes_core import HermesCore, TaskStatus
        
        hermes = HermesCore(host="127.0.0.1", port=18085)
        
        notifications = []
        hermes._send_callback = lambda url, payload: notifications.append(payload)
        hermes.register_callback("http://user-callback/notify")
        
        ws_messages = []
        mock_ws = MagicMock()
        mock_ws.send = lambda msg: ws_messages.append(json.loads(msg))
        hermes.register_ws_connection("pi-1", mock_ws)
        
        # Step 1: Pi delegates task to Hermes
        task = hermes.create_task(
            title="Write API handler",
            description="Create REST API with CRUD endpoints",
            priority="high"
        )
        
        assert task.status == TaskStatus.PENDING
        assert len(hermes.pending_queue) == 1
        
        # Step 2: Hermes processes (marks as processing via set_status or direct setattr)
        task.status = TaskStatus.PROCESSING
        
        # Step 3: Hermes completes and notifies both Pi (WS) and User (callback)
        hermes.complete_task(
            task.kanban_id,
            {"summary": "API handler created", "files": ["api.py", "models.py"]}
        )
        
        # Verify Pi got push via WebSocket
        assert len(ws_messages) == 1
        assert ws_messages[0]["kanban_id"] == task.kanban_id
        
        # Verify User got callback
        assert len(notifications) == 1
        assert notifications[0]["type"] == "task_completed"
        assert notifications[0]["result"]["summary"] == "API handler created"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])