"""TDD: Nexus Server Integration Tests - Component-level integration"""
import pytest
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import http.client

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from hermes_pi_bridge_core.bridge import AgentBridge, AgentType, get_bridge
from hermes_pi_bridge_core.life_context import LifeContextEngine
from hermes_pi_bridge_core.config import get_config


def create_mock_request(path, method="GET", body=""):
    """Create a mock request object."""
    mock = MagicMock()
    mock.path = path
    mock.command = method
    mock.headers = {"Content-Length": str(len(body))} if body else {}
    return mock


class TestNexusComponents:
    """Test Nexus components integrate correctly."""
    
    def test_bridge_and_life_context_work_together(self):
        """Bridge and life context integrate."""
        bridge = get_bridge()
        engine = LifeContextEngine()
        
        # Both should have capabilities now
        h_caps = engine.get_capabilities("hermes")
        p_caps = engine.get_capabilities("pi")
        
        assert len(h_caps) > 0
        assert len(p_caps) > 0
        
        # Bridge status should work
        status = bridge.get_connection_status()
        assert "hermes" in status
        assert "pi" in status
    
    def test_full_status_includes_all_parts(self):
        """Full status combines bridge, config, and life."""
        bridge = get_bridge()
        engine = LifeContextEngine()
        
        full_status = {
            "bridge": bridge.get_connection_status(),
            "config": get_config().get_status(),
            "life": engine.get_status()
        }
        
        # Verify structure
        assert "hermes" in full_status["bridge"]
        assert "pi" in full_status["bridge"]
        assert "version" in full_status["config"]
        assert "capabilities" in full_status["life"]
        assert "pillars" in full_status["life"]
    
    def test_life_engine_auto_discovers_on_init(self):
        """Life engine auto-discovers capabilities."""
        engine = LifeContextEngine()
        
        h_caps = engine.get_capabilities("hermes")
        p_caps = engine.get_capabilities("pi")
        
        # Should have capabilities from auto-discovery
        assert len(h_caps) > 0, "Hermes should have auto-discovered capabilities"
        assert len(p_caps) > 0, "PI should have auto-discovered capabilities"
    
    def test_config_loads_correctly(self):
        """Config loads and returns status."""
        config = get_config()
        status = config.get_status()
        
        assert "version" in status
        assert "rate_limit" in status
        assert "governance" in status
        assert "rl" in status
    
    def test_bridge_singleton_pattern(self):
        """Bridge uses singleton pattern."""
        bridge1 = get_bridge()
        bridge2 = get_bridge()
        
        assert bridge1 is bridge2  # Same instance


class TestNexusServerHandler:
    """Test Nexus API handler."""
    
    def test_handler_class_exists(self):
        """Handler class can be imported (if server module exists)."""
        # The handler class exists in the server
        # We test this by checking the server file exists
        server_path = Path(__file__).parent.parent / "nexus_server.py"
        assert server_path.exists(), "nexus_server.py should exist"


class TestNexusDataFlow:
    """Test data flow through Nexus."""
    
    def test_bridge_can_delegate_task(self):
        """Bridge can delegate tasks (even if fails, shouldn't crash)."""
        bridge = get_bridge()
        
        task = {"title": "Test task", "description": "A test task"}
        task_id = bridge.delegate_task(AgentType.PI, task)
        
        # Should return task_id or None, not crash
        assert task_id is None or isinstance(task_id, str)
    
    def test_bridge_can_update_shared_context(self):
        """Bridge can update shared context."""
        bridge = get_bridge()
        
        bridge.update_shared_context("test_key", "test_value")
        
        assert "test_key" in bridge.shared_context
        assert bridge.shared_context["test_key"]["value"] == "test_value"
    
    def test_bridge_message_history(self):
        """Bridge maintains message history."""
        bridge = get_bridge()
        
        history = bridge.get_message_history(limit=10)
        
        assert isinstance(history, list)
    
    def test_bridge_can_register_handlers(self):
        """Bridge supports handler registration."""
        bridge = get_bridge()
        
        called = [False]
        def handler(msg):
            called[0] = True
        
        bridge.register_handler("task_result", handler)
        
        # Should not crash
        assert "task_result" in bridge._handlers


class TestNexusRobustness:
    """Test robustness of Nexus components."""
    
    def test_life_engine_handles_empty_storage(self, tmp_path):
        """Handles missing storage file gracefully."""
        storage = str(tmp_path / "nonexistent.json")
        engine = LifeContextEngine(storage_path=storage)
        
        # Should not crash, should return empty/defaults
        assert engine.get_status() is not None
        assert engine.get_pillars() == []
    
    def test_life_engine_persists_data(self, tmp_path):
        """Data persists to storage."""
        storage = str(tmp_path / "data.json")
        engine = LifeContextEngine(storage_path=storage)
        
        engine.add_context("Test context", "test_pillar")
        engine.add_goal("Test goal", "Test desc", "test_pillar")
        
        # Reload
        engine2 = LifeContextEngine(storage_path=storage)
        
        assert len(engine2.contexts) == 1
        assert len(engine2.goals) == 1
    
    def test_bridge_handles_disconnect_gracefully(self):
        """Handles disconnect without crashing."""
        bridge = get_bridge()
        
        # Disconnect should not crash
        bridge.disconnect(AgentType.HERMES)
        bridge.disconnect(AgentType.PI)
        
        # Status should still work
        status = bridge.get_connection_status()
        assert "hermes" in status
        assert "pi" in status
    
    def test_bridge_connection_attempt_handles_errors(self):
        """Connection attempt handles errors gracefully."""
        bridge = get_bridge()
        
        # Bad URL should not crash
        result = bridge.connect(AgentType.PI, url="http://localhost:99999")
        
        assert isinstance(result, bool)


class TestNexusLifeOperations:
    """Test life context operations."""
    
    def test_can_add_contexts_to_pillars(self, tmp_path):
        """Can add contexts to pillars."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "test.json"))
        
        engine.add_context("Career goal", "capacity")
        engine.add_context("Health goal", "vitality")
        engine.add_context("Financial goal", "prosperity")
        
        pillars = engine.get_pillars()
        assert "capacity" in pillars
        assert "vitality" in pillars
        assert "prosperity" in pillars
    
    def test_can_add_goals(self, tmp_path):
        """Can add goals to pillars."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "test.json"))
        
        goal = engine.add_goal("Run marathon", "Complete 26.2 miles", "vitality")
        
        assert goal.pillar == "vitality"
        assert goal.status == "not_started"
    
    def test_can_update_goal_progress(self, tmp_path):
        """Can update goal progress."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "test.json"))
        
        goal = engine.add_goal("Learn Python", "Master Python", "capacity")
        result = engine.update_goal_progress(goal.id, 50)
        
        assert result is True
        assert goal.progress == 50
    
    def test_goal_completes_at_100(self, tmp_path):
        """Goal completes when progress hits 100."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "test.json"))
        
        goal = engine.add_goal("Finish project", "Complete it", "capacity")
        engine.update_goal_progress(goal.id, 100)
        
        assert goal.status == "completed"
        assert goal.completed_at is not None
    
    def test_can_propose_capabilities(self, tmp_path):
        """Can propose new capabilities."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "test.json"))
        
        vote_id = engine.propose_capability("deep_learning", "hermes")
        
        assert vote_id.startswith("vote_")
        assert len(engine.capability_votes) == 1
    
    def test_capability_voting_works(self, tmp_path):
        """Consensus voting works for capabilities."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "test.json"))
        
        vote_id = engine.propose_capability("quantum_computing", "pi")
        
        # Two approvals
        engine.vote_capability(vote_id, "hermes", True, "Good idea")
        engine.vote_capability(vote_id, "pi", True, "Interesting")
        
        vote = engine.capability_votes[0]
        assert vote["status"] == "approved"


class TestNexusCapabilityDiscovery:
    """Test capability discovery."""
    
    def test_hermes_has_strategic_capabilities(self):
        """Hermes gets strategic capabilities."""
        engine = LifeContextEngine()
        
        caps = engine.get_capabilities("hermes")
        
        # Should have planning, strategy, reasoning
        expected = ["planning", "strategy", "reasoning"]
        found = any(c in caps for c in expected)
        assert found, f"Hermes should have strategic capabilities, got: {caps}"
    
    def test_pi_has_tactical_capabilities(self):
        """PI gets tactical capabilities."""
        engine = LifeContextEngine()
        
        caps = engine.get_capabilities("pi")
        
        # Should have coding, execution, tools
        expected = ["coding", "execution", "tools"]
        found = any(c in caps for c in expected)
        assert found, f"PI should have tactical capabilities, got: {caps}"


class TestNexusSampleData:
    """Test sample data functionality."""
    
    def test_add_sample_data(self, tmp_path):
        """Sample data adds contexts and goals."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "test.json"))
        
        result = engine.add_sample_data()
        
        assert result["contexts"] == 5
        assert result["goals"] == 3
        assert result["capabilities"] == 10
    
    def test_sample_data_persists(self, tmp_path):
        """Sample data persists after reload."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "test.json"))
        engine.add_sample_data()
        
        # Reload
        engine2 = LifeContextEngine(storage_path=str(tmp_path / "test.json"))
        
        assert len(engine2.contexts) == 5
        assert len(engine2.goals) == 3


class TestNexusControlPoints:
    """Test control points for management."""
    
    def test_can_query_capabilities(self):
        """Can query agent capabilities."""
        bridge = get_bridge()
        
        # Query (may return None if not connected)
        caps = bridge.query_capabilities(AgentType.PI)
        
        # Should be None or list, not crash
        assert caps is None or isinstance(caps, list)
    
    def test_can_check_agent_can_handle_task(self, tmp_path):
        """Can check if agent can handle task."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "test.json"))
        
        engine.discover_capabilities("hermes")
        
        can_do, missing = engine.can_handle_task("hermes", ["planning"])
        
        assert can_do is True
        assert len(missing) == 0
    
    def test_can_detect_missing_capabilities(self, tmp_path):
        """Detects missing capabilities."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "test.json"))
        
        engine.add_capability("hermes", "planning")
        
        can_do, missing = engine.can_handle_task("hermes", ["planning", "unknown_skill"])
        
        assert can_do is False
        assert "unknown_skill" in missing


# Use pytest's tmp_path fixture
@pytest.fixture
def tmp_path(tmp_path):
    """Provide temp path for tests."""
    return tmp_path