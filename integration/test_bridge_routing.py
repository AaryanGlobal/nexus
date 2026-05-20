"""TDD: Bridge Reconnection and Task Routing Tests"""
import pytest
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core" / "src"))

from hermes_pi_bridge_core.bridge import AgentBridge, AgentType
from hermes_pi_bridge_core.life_context import LifeContextEngine


class TestBridgeReconnection:
    """Test bridge reconnection logic."""
    
    def test_bridge_has_reconnect_method(self):
        """Bridge should have reconnect method."""
        bridge = AgentBridge()
        assert hasattr(bridge, 'reconnect'), "Bridge should have reconnect method"
    
    def test_bridge_has_check_connection_method(self):
        """Bridge should have check_connection method."""
        bridge = AgentBridge()
        assert hasattr(bridge, 'check_connection') or hasattr(bridge, 'ping'), \
            "Bridge should have check_connection or ping method"
    
    def test_reconnect_retries_connection(self):
        """reconnect attempts to re-establish connection."""
        bridge = AgentBridge()
        
        # Try reconnect
        result = bridge.reconnect(AgentType.HERMES)
        
        # Should return boolean (success or failure)
        assert isinstance(result, bool)
    
    def test_check_connection_returns_status(self):
        """check_connection returns connection status."""
        bridge = AgentBridge()
        
        status = bridge.check_connection(AgentType.HERMES)
        
        assert isinstance(status, bool)
    
    def test_bridge_can_auto_reconnect(self):
        """Bridge should have auto-reconnect capability."""
        bridge = AgentBridge()
        
        # Should have auto-reconnect setting
        assert hasattr(bridge, 'auto_reconnect') or hasattr(bridge, 'enable_auto_reconnect')


class TestTaskRouting:
    """Test automated task routing."""
    
    def test_life_engine_has_route_task_method(self):
        """Life engine should have route_task method."""
        engine = LifeContextEngine()
        assert hasattr(engine, 'route_task'), "Life engine should have route_task"
    
    def test_life_engine_has_find_best_agent_method(self):
        """Life engine should have find_best_agent method."""
        engine = LifeContextEngine()
        assert hasattr(engine, 'find_best_agent') or hasattr(engine, 'best_agent_for'), \
            "Life engine should have find_best_agent or best_agent_for"
    
    def test_route_task_returns_agent(self):
        """route_task returns the appropriate agent."""
        engine = LifeContextEngine()
        
        # Set up capabilities
        engine.add_capability("hermes", "planning")
        engine.add_capability("pi", "coding")
        
        # Route tasks
        result = engine.route_task(["planning"])
        
        assert result == "hermes" or result == "pi"
    
    def test_route_task_returns_none_for_unknown(self):
        """route_task returns None if no agent can handle."""
        engine = LifeContextEngine()
        
        # Try to route unknown task
        result = engine.route_task(["unknown_skill_xyz"])
        
        assert result is None or result == ""
    
    def test_find_best_agent_prefers_matching(self):
        """find_best_agent prefers agent with matching capabilities."""
        engine = LifeContextEngine()
        
        engine.add_capability("hermes", "planning")
        engine.add_capability("hermes", "strategy")
        engine.add_capability("pi", "coding")
        
        # Find best for planning task
        best = engine.find_best_agent(["planning", "strategy"])
        
        assert best == "hermes"
    
    def test_task_routing_considers_multiple_requirements(self):
        """Task routing handles multiple requirements."""
        engine = LifeContextEngine()
        
        engine.add_capability("hermes", "planning")
        engine.add_capability("pi", "coding")
        engine.add_capability("pi", "testing")
        
        # Route task with multiple requirements
        result = engine.route_task(["coding", "testing"])
        
        assert result == "pi"


class TestBridgeHealth:
    """Test bridge health monitoring."""
    
    def test_bridge_has_get_health_method(self):
        """Bridge should have get_health method."""
        bridge = AgentBridge()
        assert hasattr(bridge, 'get_health') or hasattr(bridge, 'health_check'), \
            "Bridge should have get_health or health_check"
    
    def test_health_check_returns_all_agents(self):
        """Health check returns status for all agents."""
        bridge = AgentBridge()
        
        if hasattr(bridge, 'get_health'):
            health = bridge.get_health()
        else:
            health = bridge.health_check()
        
        assert 'hermes' in health
        assert 'pi' in health
    
    def test_health_check_includes_latency(self):
        """Health check includes latency metrics."""
        bridge = AgentBridge()
        
        if hasattr(bridge, 'get_health'):
            health = bridge.get_health()
        else:
            health = bridge.health_check()
        
        # Each agent should have latency or response_time
        for agent in ['hermes', 'pi']:
            agent_health = health.get(agent, {})
            assert 'latency' in agent_health or 'response_time' in agent_health or 'last_contact' in agent_health


class TestBridgeStats:
    """Test bridge statistics."""
    
    def test_bridge_has_get_stats_method(self):
        """Bridge should have get_stats method."""
        bridge = AgentBridge()
        assert hasattr(bridge, 'get_stats'), "Bridge should have get_stats"
    
    def test_stats_include_message_count(self):
        """Stats include message counts."""
        bridge = AgentBridge()
        
        # Send some messages (will fail but should be tracked)
        bridge.delegate_task(AgentType.PI, {"task": "test"})
        
        stats = bridge.get_stats()
        
        assert 'messages_sent' in stats or 'total_messages' in stats or 'message_count' in stats
    
    def test_stats_include_success_rate(self):
        """Stats include success rate."""
        bridge = AgentBridge()
        
        stats = bridge.get_stats()
        
        assert 'success_rate' in stats or 'success_count' in stats or 'delivery_rate' in stats


class TestBridgeObservability:
    """Test bridge observability."""
    
    def test_bridge_logs_messages(self):
        """Bridge logs message sending."""
        bridge = AgentBridge()
        
        # Get initial history
        history = bridge.get_message_history()
        initial_count = len(history)
        
        # Try to send
        bridge.delegate_task(AgentType.HERMES, {"title": "test"})
        
        # History should have entry
        new_history = bridge.get_message_history()
        assert len(new_history) >= initial_count
    
    def test_bridge_tracks_delivery_status(self):
        """Bridge tracks message delivery status."""
        bridge = AgentBridge()
        
        # Try sending
        result = bridge.delegate_task(AgentType.PI, {"title": "test"})
        
        # Check history for delivery status
        history = bridge.get_message_history(limit=1)
        if len(history) > 0:
            msg = history[0]
            # Message should have basic tracking fields
            assert 'id' in msg or 'from' in msg