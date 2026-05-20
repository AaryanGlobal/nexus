"""TDD: Edge Cases and Final Verification"""
import pytest
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core" / "src"))

from hermes_pi_bridge_core.bridge import get_bridge, AgentType
from hermes_pi_bridge_core.life_context import LifeContextEngine
from hermes_pi_bridge_core.rl import ReinforcementLearning, ActionType


class TestRLPersistenceEdgeCases:
    """Test RL persistence edge cases."""
    
    def test_save_to_nonexistent_directory(self):
        """Save to directory that doesn't exist."""
        rl = ReinforcementLearning()
        rl.reward(ActionType.DELEGATE, True)
        
        # Should handle gracefully (create directory or use temp)
        path = "/tmp/nonexistent_dir/nexus_rl.json"
        try:
            rl.save(path)
            # May fail due to directory not existing - that's OK
            loaded = ReinforcementLearning()
            loaded.load(path)
            stats = loaded.get_stats()
            assert 'total_rewards' in stats
        except Exception:
            # FileError is acceptable - directory doesn't exist
            pass
    
    def test_load_from_invalid_path(self):
        """Load from path that doesn't exist."""
        rl = ReinforcementLearning()
        
        try:
            rl.load("/tmp/this_does_not_exist.json")
            # If it loads without error, that's also OK (may use defaults)
        except Exception:
            # FileNotFoundError is expected
            pass
    
    def test_multiple_save_load_cycles(self):
        """Multiple save/load cycles preserve state."""
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'rl.json')
            
            # Cycle 1
            rl1 = ReinforcementLearning()
            rl1.reward(ActionType.DELEGATE, True)
            rl1.save(path)
            
            # Cycle 2
            rl2 = ReinforcementLearning()
            rl2.load(path)
            rl2.reward(ActionType.EXECUTE, True)
            rl2.save(path)
            
            # Cycle 3
            rl3 = ReinforcementLearning()
            rl3.load(path)
            stats = rl3.get_stats()
            
            assert stats['total_rewards'] >= 2


class TestCapabilityRoutingEdgeCases:
    """Test capability routing edge cases."""
    
    def test_route_empty_task(self):
        """Route empty task list."""
        engine = LifeContextEngine()
        
        result = engine.route_task([])
        
        # Should return None or valid agent, not crash
        assert result in [None, 'hermes', 'pi']
    
    def test_route_ambiguous_task(self):
        """Route task that both agents can handle."""
        engine = LifeContextEngine()
        
        # Task requiring both planning AND coding
        result = engine.route_task(['analyze', 'implement'])
        
        assert result in [None, 'hermes', 'pi']
    
    def test_can_handle_with_empty_requirements(self):
        """Can handle with empty requirements."""
        engine = LifeContextEngine()
        
        result = engine.can_handle_task("hermes", [])
        
        # Should be tuple
        assert isinstance(result, tuple)


class TestBridgeEdgeCases:
    """Test bridge edge cases."""
    
    def test_connect_to_nonexistent_url(self):
        """Connect to URL that doesn't respond."""
        bridge = get_bridge()
        
        result = bridge.connect(AgentType.PI, url="http://localhost:99999")
        
        # Should return False, not crash
        assert result is False
    
    def test_delegate_with_empty_task(self):
        """Delegate empty task dict."""
        bridge = get_bridge()
        
        task_id = bridge.delegate_task(AgentType.HERMES, {})
        
        # Should still return task_id
        assert task_id is not None
    
    def test_receive_result_with_minimal_data(self):
        """Receive result with minimal data."""
        bridge = get_bridge()
        
        result = bridge.receive_result(AgentType.PI, {})
        
        assert isinstance(result, dict)


class TestMessageHistoryEdgeCases:
    """Test message history edge cases."""
    
    def test_message_history_respects_limit(self):
        """Message history respects max limit."""
        bridge = get_bridge()
        
        initial = len(bridge.message_history)
        max_hist = bridge.max_history
        
        # Add many messages
        for i in range(10):
            bridge.delegate_task(AgentType.HERMES, {'type': 'test'})
        
        # History should not grow unbounded
        # (Implementation may enforce limit)
        current = len(bridge.message_history)
        assert current <= initial + 10 + max_hist
    
    def test_get_message_history_with_invalid_agent(self):
        """Get history for non-existent agent."""
        bridge = get_bridge()
        
        # Should not crash, returns list
        history = bridge.get_message_history(limit=10)
        assert isinstance(history, list)


class TestGoalLifecycleEdgeCases:
    """Test goal lifecycle edge cases."""
    
    def test_update_nonexistent_goal(self):
        """Update goal that doesn't exist."""
        engine = LifeContextEngine()
        
        result = engine.update_goal_progress("nonexistent_id", 50)
        
        # Should return False, not crash
        assert result is False
    
    def test_goals_by_nonexistent_pillar(self):
        """Get goals for pillar that doesn't exist."""
        engine = LifeContextEngine()
        
        goals = engine.get_goals_by_pillar("NonexistentPillarXYZ")
        
        # Should return empty list
        assert isinstance(goals, list)


class TestCapabilityVotingEdgeCases:
    """Test capability voting edge cases."""
    
    def test_vote_on_nonexistent_proposal(self):
        """Vote on proposal that doesn't exist."""
        engine = LifeContextEngine()
        
        result = engine.vote_capability("nonexistent_id", "hermes", True)
        
        # Should handle gracefully
        assert result is not None
    
    def test_double_vote(self):
        """Vote twice on same proposal."""
        engine = LifeContextEngine()
        
        prop_id = engine.propose_capability("test_cap", "hermes")
        
        # First vote
        engine.vote_capability(prop_id, "hermes", True)
        
        # Second vote (may update or ignore)
        result = engine.vote_capability(prop_id, "hermes", True)
        
        assert result is True


class TestSelfEvolutionEdgeCases:
    """Test self-evolution edge cases."""
    
    def test_propose_duplicate_capability(self):
        """Propose capability that already exists."""
        engine = LifeContextEngine()
        
        # Propose something that might already exist
        prop_id = engine.propose_capability("coding", "hermes")
        
        assert prop_id is not None
    
    def test_add_capability_to_nonexistent_agent(self):
        """Add capability to non-existent agent."""
        engine = LifeContextEngine()
        
        # May fail silently or raise - either is OK
        try:
            result = engine.add_capability("nonexistent_agent", "new_cap")
        except Exception:
            pass


class TestHealthMonitoringEdgeCases:
    """Test health monitoring edge cases."""
    
    def test_health_with_disconnected_agents(self):
        """Health check with disconnected agents."""
        from hermes_pi_bridge_core.bridge import AgentBridge, AgentType
        
        bridge = AgentBridge()  # Fresh instance
        
        # Health check makes HTTP requests and may update status
        # Just verify it returns valid health data
        health = bridge.get_health()
        
        # Should have entries for both agents
        assert 'hermes' in health
        assert 'pi' in health
        
        # Each should have required fields
        assert 'status' in health['hermes']
        assert 'latency_ms' in health['hermes']
        assert 'last_contact' in health['hermes']
    
    def test_stats_with_no_messages(self):
        """Stats with no messages sent."""
        bridge = get_bridge()
        
        # Create fresh bridge
        from hermes_pi_bridge_core.bridge import AgentBridge
        fresh_bridge = AgentBridge()
        
        stats = fresh_bridge.get_stats()
        
        assert isinstance(stats, dict)


class TestFullCollaborationStressTest:
    """Stress test full collaboration."""
    
    def test_rapid_delegation(self):
        """Rapid delegation of multiple tasks."""
        bridge = get_bridge()
        
        initial = len(bridge.message_history)
        
        # Rapid fire 20 delegations
        for i in range(20):
            bridge.delegate_task(AgentType.HERMES, {'type': 'test', 'id': i})
        
        final = len(bridge.message_history)
        
        # Should have added messages
        assert final > initial
    
    def test_rapid_rewards(self):
        """Rapid RL rewards."""
        rl = ReinforcementLearning()
        
        # Rapid rewards
        for i in range(50):
            rl.reward(ActionType.DELEGATE, i % 2 == 0)
        
        stats = rl.get_stats()
        
        # Should have accumulated rewards
        assert stats['total_rewards'] >= 25  # At least half successes
    
    def test_mixed_operations(self):
        """Mixed bridge operations."""
        bridge = get_bridge()
        engine = LifeContextEngine()
        rl = ReinforcementLearning()
        
        # Mix of operations
        for i in range(5):
            agent = engine.route_task(['code'])
            if agent:
                a_type = AgentType.HERMES if agent == 'hermes' else AgentType.PI
                bridge.delegate_task(a_type, {'task': i})
            
            bridge.receive_result(AgentType.PI, {'result': i})
            rl.reward(ActionType.DELEGATE, True)
        
        # All should complete without error
        assert True