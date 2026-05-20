"""TDD: Agent Bridge Tests"""
import pytest
import tempfile
from datetime import datetime

from hermes_pi_bridge_core.bridge import (
    AgentBridge, AgentType, AgentConnection, AgentMessage,
    MessageType, get_bridge
)


class TestAgentConnection:
    """Test agent connection."""
    
    def test_connection_initialization(self):
        """Connection initializes with defaults."""
        conn = AgentConnection(agent_type=AgentType.HERMES, url="http://localhost:8080")
        assert conn.agent_type == AgentType.HERMES
        assert conn.url == "http://localhost:8080"
        assert conn.status == "disconnected"


class TestAgentMessage:
    """Test agent messages."""
    
    def test_message_creation(self):
        """Can create messages."""
        msg = AgentMessage(
            id="test_1",
            from_agent="nexus",
            to_agent="hermes",
            type=MessageType.TASK_DELEGATE.value,
            content={"task": "test"}
        )
        assert msg.id == "test_1"
        assert msg.from_agent == "nexus"
        assert msg.type == "task_delegate"


class TestAgentBridge:
    """Test agent bridge."""
    
    def test_bridge_initialization(self):
        """Bridge initializes with both agents."""
        bridge = AgentBridge()
        assert AgentType.HERMES in bridge.connections
        assert AgentType.PI in bridge.connections
    
    def test_singleton(self):
        """get_bridge returns singleton."""
        b1 = get_bridge()
        b2 = get_bridge()
        assert b1 is b2
    
    def test_update_shared_context(self):
        """Can update shared context."""
        bridge = AgentBridge()
        bridge.update_shared_context("test_key", "test_value")
        
        assert "test_key" in bridge.shared_context
        assert bridge.shared_context["test_key"]["value"] == "test_value"
    
    def test_message_history(self):
        """Can track message history."""
        bridge = AgentBridge()
        
        msg = AgentMessage(
            id="msg_1",
            from_agent="nexus",
            to_agent="hermes",
            type=MessageType.TASK_DELEGATE.value,
            content={}
        )
        bridge._add_to_history(msg)
        
        history = bridge.get_message_history()
        assert len(history) == 1
        assert history[0]["id"] == "msg_1"
    
    def test_connection_status(self):
        """Can get connection status."""
        bridge = AgentBridge()
        status = bridge.get_connection_status()
        
        assert "hermes" in status
        assert "pi" in status
        assert status["hermes"]["status"] == "disconnected"
    
    def test_register_handler(self):
        """Can register message handlers."""
        bridge = AgentBridge()
        
        received = []
        def handler(msg):
            received.append(msg)
        
        bridge.register_handler(MessageType.TASK_RESULT.value, handler)
        
        # Simulate receiving a result
        result = {"task_id": "123", "success": True}
        bridge.receive_result(AgentType.HERMES, result)
        
        assert len(received) == 1
        assert received[0]["success"] is True


class TestCapabilityQueries:
    """Test capability queries."""
    
    def test_query_capabilities_disconnected(self):
        """Returns None when disconnected."""
        bridge = AgentBridge()
        caps = bridge.query_capabilities(AgentType.HERMES)
        assert caps is None


class TestMessageFiltering:
    """Test message history filtering."""
    
    def test_filter_by_agent(self):
        """Can filter history by agent."""
        bridge = AgentBridge()
        
        msg1 = AgentMessage("1", "nexus", "hermes", "task_delegate", {})
        msg2 = AgentMessage("2", "pi", "nexus", "task_result", {})
        bridge._add_to_history(msg1)
        bridge._add_to_history(msg2)
        
        hermes_msgs = bridge.get_message_history(agent=AgentType.HERMES)
        assert len(hermes_msgs) == 1
        assert hermes_msgs[0]["from"] == "nexus"


class TestContextSync:
    """Test context synchronization."""
    
    def test_sync_context_no_connection(self):
        """Fails gracefully when not connected."""
        bridge = AgentBridge()
        result = bridge.sync_context(AgentType.HERMES)
        assert result is False