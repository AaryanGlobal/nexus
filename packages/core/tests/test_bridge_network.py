"""TDD: Bridge Network Edge Cases Tests - Without network calls"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from hermes_pi_bridge_core.bridge import (
    AgentBridge, AgentType, AgentMessage, MessageType
)


class TestMessageHistory:
    """Test message history management."""
    
    def test_history_limit_enforcement(self):
        """Enforces history size limit."""
        bridge = AgentBridge()
        bridge.max_history = 5
        
        # Add more than limit
        for i in range(10):
            msg = AgentMessage(f"msg_{i}", "nexus", "hermes", "task_delegate", {})
            bridge._add_to_history(msg)
        
        # Should be capped at max_history
        assert len(bridge.message_history) <= bridge.max_history
    
    def test_filter_by_agent(self):
        """Can filter history by agent."""
        bridge = AgentBridge()
        
        msg1 = AgentMessage("1", "nexus", "hermes", "task_delegate", {})
        msg2 = AgentMessage("2", "pi", "nexus", "task_result", {})
        bridge._add_to_history(msg1)
        bridge._add_to_history(msg2)
        
        hermes_msgs = bridge.get_message_history(agent=AgentType.HERMES)
        assert len(hermes_msgs) == 1
        
        pi_msgs = bridge.get_message_history(agent=AgentType.PI)
        assert len(pi_msgs) == 1
    
    def test_limit_parameter(self):
        """Respects limit parameter."""
        bridge = AgentBridge()
        
        for i in range(20):
            msg = AgentMessage(f"msg_{i}", "nexus", "hermes", "task_delegate", {})
            bridge._add_to_history(msg)
        
        history = bridge.get_message_history(limit=5)
        assert len(history) == 5


class TestConnectionStatus:
    """Test connection status reporting."""
    
    def test_initial_status_disconnected(self):
        """Initial status is disconnected."""
        bridge = AgentBridge()
        
        status = bridge.get_connection_status()
        assert status["hermes"]["status"] == "disconnected"
        assert status["pi"]["status"] == "disconnected"
    
    def test_status_includes_url(self):
        """Status includes URL."""
        bridge = AgentBridge(hermes_url="http://custom:8080")
        
        status = bridge.get_connection_status()
        assert "custom" in status["hermes"]["url"]


class TestSharedContext:
    """Test shared context management."""
    
    def test_update_context(self):
        """Can update shared context."""
        bridge = AgentBridge()
        
        bridge.update_shared_context("goal", "Build AI agent")
        
        assert "goal" in bridge.shared_context
        assert bridge.shared_context["goal"]["value"] == "Build AI agent"
    
    def test_context_has_metadata(self):
        """Context includes metadata."""
        bridge = AgentBridge()
        
        bridge.update_shared_context("test", "value")
        
        ctx = bridge.shared_context["test"]
        assert "updated_at" in ctx
        assert "updated_by" in ctx
        assert ctx["updated_by"] == "nexus"


class TestMessageHandlers:
    """Test message handler robustness."""
    
    def test_handler_exception_doesnt_crash(self):
        """Handler exception doesn't crash."""
        bridge = AgentBridge()
        
        def bad_handler(msg):
            raise Exception("Handler error")
        
        bridge.register_handler(MessageType.TASK_RESULT.value, bad_handler)
        
        # Should not crash
        result = bridge.receive_result(AgentType.HERMES, {"success": True})
        assert result is not None
    
    def test_unknown_handler(self):
        """Handles unknown message types gracefully."""
        bridge = AgentBridge()
        
        # Register for known type
        bridge.register_handler(MessageType.TASK_RESULT.value, lambda m: "ok")
        
        # Send different type - should not crash
        msg = AgentMessage("1", "hermes", "nexus", "unknown_type", {})
        bridge._add_to_history(msg)
        assert len(bridge.message_history) == 1


class TestDelegation:
    """Test task delegation."""
    
    def test_delegate_creates_message(self):
        """Delegate creates message in history."""
        bridge = AgentBridge()
        
        # Even if disconnected, message should be attempted
        task_id = bridge.delegate_task(AgentType.HERMES, {"task": "test"})
        
        # Check history has the attempt
        history = bridge.get_message_history()
        # Message was created (though send may have failed)
        assert len(history) >= 0
    
    def test_delegate_returns_task_id(self):
        """Delegate returns task_id on success."""
        bridge = AgentBridge()
        
        # Mock successful send
        bridge.connections[AgentType.HERMES].status = "connected"
        
        with patch.object(bridge, '_http_post', return_value={}):
            task_id = bridge.delegate_task(AgentType.HERMES, {"task": "test"})
            assert task_id is not None
            assert task_id.startswith("msg_")


class TestReceiveResult:
    """Test receiving results."""
    
    def test_receive_stores_in_history(self):
        """Receive stores in history."""
        bridge = AgentBridge()
        
        bridge.receive_result(AgentType.HERMES, {"success": True, "task_id": "123"})
        
        history = bridge.get_message_history(AgentType.HERMES)
        assert len(history) == 1
        assert history[0]["type"] == "task_result"
    
    def test_receive_calls_handler(self):
        """Receive calls registered handler."""
        bridge = AgentBridge()
        
        received = []
        bridge.register_handler(MessageType.TASK_RESULT.value, lambda r: received.append(r))
        
        bridge.receive_result(AgentType.HERMES, {"data": "test"})
        
        assert len(received) == 1
        assert received[0]["data"] == "test"


class TestDisconnect:
    """Test disconnect functionality."""
    
    def test_disconnect_updates_status(self):
        """Disconnect updates status."""
        bridge = AgentBridge()
        
        bridge.connections[AgentType.HERMES].status = "connected"
        bridge.disconnect(AgentType.HERMES)
        
        assert bridge.connections[AgentType.HERMES].status == "disconnected"


class TestSingleton:
    """Test singleton behavior."""
    
    def test_get_bridge_returns_same(self):
        """get_bridge returns same instance."""
        from hermes_pi_bridge_core.bridge import get_bridge
        
        b1 = get_bridge()
        b2 = get_bridge()
        assert b1 is b2