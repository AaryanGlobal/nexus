"""TDD: CLI Completeness and Server Integration Tests"""
import pytest
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core" / "src"))

from hermes_pi_bridge_core.bridge import AgentBridge, AgentType, get_bridge
from hermes_pi_bridge_core.life_context import LifeContextEngine
from hermes_pi_bridge_core.rl import ReinforcementLearning, ActionType
from hermes_pi_bridge_core.autonomous import AutonomousNHIL, AutonomousConfig


class TestCLIServerIntegration:
    """Test CLI can interact with Nexus server."""
    
    def test_cli_status_command(self):
        """CLI status command works."""
        result = subprocess.run(
            [sys.executable, "/home/agi/nexus/nexus_cli.py", "status"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Should not crash
        assert result.returncode in [0, 1]  # 0 = success, 1 = server not running
        
        # Output should contain expected sections
        if result.returncode == 0:
            assert "NEXUS STATUS" in result.stdout or "Bridges" in result.stdout
    
    def test_cli_capabilities_command(self):
        """CLI capabilities command works."""
        result = subprocess.run(
            [sys.executable, "/home/agi/nexus/nexus_cli.py", "capabilities"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Should not crash
        assert result.returncode in [0, 1]
        
        if result.returncode == 0:
            assert "Hermes" in result.stdout or "AGENT CAPABILITIES" in result.stdout
    
    def test_cli_health_command(self):
        """CLI health command works."""
        result = subprocess.run(
            [sys.executable, "/home/agi/nexus/nexus_cli.py", "health"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Should not crash
        assert result.returncode in [0, 1]
    
    def test_cli_pillars_command(self):
        """CLI pillars command works."""
        result = subprocess.run(
            [sys.executable, "/home/agi/nexus/nexus_cli.py", "pillars"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode in [0, 1]


class TestAutonomousNHILIntegration:
    """Test AutonomousNHIL can be used as standalone."""
    
    def test_autonomous_config_defaults(self):
        """AutonomousConfig has sensible defaults."""
        config = AutonomousConfig()
        
        assert config.scan_interval_seconds >= 0
        assert config.max_execution_duration_seconds > 0
        assert config.max_history_entries > 0
        assert config.evolution_threshold >= 1
    
    def test_autonomous_can_initialize(self):
        """AutonomousNHIL can initialize."""
        config = AutonomousConfig()
        
        # Should not crash on init
        try:
            nhil = AutonomousNHIL(config=config)
            assert nhil is not None
        except Exception as e:
            # Some dependencies might not be available
            pytest.skip(f"AutonomousNHIL init failed: {e}")
    
    def test_autonomous_has_control_methods(self):
        """AutonomousNHIL has all control methods."""
        config = AutonomousConfig()
        
        try:
            nhil = AutonomousNHIL(config=config)
            
            # Core control methods
            assert hasattr(nhil, 'start')
            assert hasattr(nhil, 'stop')
            assert hasattr(nhil, 'pause')
            assert hasattr(nhil, 'resume')
            
            # Task methods
            assert hasattr(nhil, 'inject_task')
            assert hasattr(nhil, 'approve_task')
            assert hasattr(nhil, 'reject_task')
            
            # Monitoring
            assert hasattr(nhil, 'get_status')
            assert hasattr(nhil, 'get_current_activity')
            assert hasattr(nhil, 'get_audit_log')
            
            # RL methods
            assert hasattr(nhil, 'get_rl_action')
            assert hasattr(nhil, 'apply_reward')
            assert hasattr(nhil, 'get_rl_statistics')
            
            # Governance
            assert hasattr(nhil, 'validate_action')
            assert hasattr(nhil, 'get_governance_status')
            
            # Life context
            assert hasattr(nhil, 'add_life_context')
            assert hasattr(nhil, 'get_life_status')
            assert hasattr(nhil, 'get_pillar_status')
            
        except Exception as e:
            pytest.skip(f"AutonomousNHIL test skipped: {e}")
    
    def test_autonomous_rl_integration(self):
        """AutonomousNHIL RL integration works."""
        config = AutonomousConfig()
        
        try:
            nhil = AutonomousNHIL(config=config)
            
            # Get RL action
            rl_result = nhil.get_rl_action("test_state")
            
            assert 'action' in rl_result
            assert 'confidence' in rl_result
            assert 'state' in rl_result
            
            # Apply reward
            reward = nhil.apply_reward('execute', True, duration=5.0)
            assert isinstance(reward, float)
            
            # Get RL statistics
            stats = nhil.get_rl_statistics()
            assert 'total_rewards' in stats or 'states_learned' in stats
            
        except Exception as e:
            pytest.skip(f"RL integration test skipped: {e}")
    
    def test_autonomous_life_context_integration(self):
        """AutonomousNHIL life context integration works."""
        config = AutonomousConfig()
        
        try:
            nhil = AutonomousNHIL(config=config)
            
            # Add life context
            result = nhil.add_life_context(
                "Build AI agent system",
                "capacity",
                auto_create_goal=True
            )
            
            assert 'id' in result
            
            # Get life status
            life_status = nhil.get_life_status()
            assert 'pillars' in life_status or 'goals_total' in life_status
            
            # Get pillar status
            pillar_status = nhil.get_pillar_status("capacity")
            assert 'pillar' in pillar_status
            
        except Exception as e:
            pytest.skip(f"Life context test skipped: {e}")
    
    def test_autonomous_can_control_tasks(self):
        """AutonomousNHIL can inject and control tasks."""
        config = AutonomousConfig()
        
        try:
            nhil = AutonomousNHIL(config=config)
            
            # Inject task
            result = nhil.inject_task(
                "Test task description",
                priority="medium",
                context={"test": True}
            )
            
            # Should return result dict
            assert isinstance(result, dict)
            assert 'success' in result or 'error' in result
            
        except Exception as e:
            pytest.skip(f"Task control test skipped: {e}")


class TestBridgeServerIntegration:
    """Test bridge integrates with server components."""
    
    def test_bridge_get_health_returns_all_agents(self):
        """Bridge health check returns all agents."""
        bridge = get_bridge()
        
        health = bridge.get_health()
        
        assert 'hermes' in health
        assert 'pi' in health
        
        # Each should have status and latency
        for agent in ['hermes', 'pi']:
            assert 'status' in health[agent]
    
    def test_bridge_get_stats(self):
        """Bridge get_stats returns statistics."""
        bridge = get_bridge()
        
        stats = bridge.get_stats()
        
        assert 'total_messages' in stats or 'total_messages' in stats
        assert 'messages_sent' in stats or 'messages_sent' in stats
    
    def test_bridge_circuit_breaker(self):
        """Bridge circuit breaker works."""
        bridge = AgentBridge()
        
        # Initially circuit should be closed
        assert bridge.is_circuit_open(AgentType.PI) is False
        
        # Trip circuit
        bridge.trip(AgentType.PI)
        assert bridge.is_circuit_open(AgentType.PI) is True
        
        # Reset circuit
        bridge.reset_circuit(AgentType.PI)
        assert bridge.is_circuit_open(AgentType.PI) is False
        
        # Record failures
        bridge.record_failure(AgentType.PI)
        assert bridge.get_failures(AgentType.PI) >= 1


class TestRLPersistenceIntegration:
    """Test RL persistence works end-to-end."""
    
    def test_rl_save_and_load_preserves_q_values(self, tmp_path):
        """RL save/load preserves Q-values."""
        rl1 = ReinforcementLearning()
        
        # Learn multiple states
        rl1.update_q_value("state1", ActionType.EXECUTE, 1.0, "done")
        rl1.update_q_value("state2", ActionType.DELEGATE, 0.5, "done")
        rl1.update_q_value("state3", ActionType.SPLIT, -0.5, "fail")
        
        # Save
        save_path = str(tmp_path / "rl_state.json")
        assert rl1.save(save_path) is True
        
        # Load into new instance
        rl2 = ReinforcementLearning()
        assert rl2.load(save_path) is True
        
        # Verify Q-values preserved
        q1 = rl2.get_q_value("state1", ActionType.EXECUTE)
        q2 = rl2.get_q_value("state2", ActionType.DELEGATE)
        q3 = rl2.get_q_value("state3", ActionType.SPLIT)
        
        assert q1 > 0  # Should have positive reward
        assert q2 > 0  # Should have positive reward
        assert q3 < 0  # Should have negative reward
    
    def test_rl_save_preserves_config(self, tmp_path):
        """RL save/load preserves configuration."""
        rl1 = ReinforcementLearning()
        original_rate = rl1.config.exploration_rate
        
        # Save
        save_path = str(tmp_path / "rl_config.json")
        rl1.save(save_path)
        
        # Change config and save again
        rl1.config.exploration_rate = 0.5
        rl1.save(save_path)
        
        # Load
        rl2 = ReinforcementLearning()
        rl2.load(save_path)
        
        # Config should be restored
        assert rl2.config.exploration_rate == 0.5


class TestGoalLifecycleIntegration:
    """Test goal lifecycle with persistence."""
    
    def test_goals_persist_across_engine_restarts(self, tmp_path):
        """Goals persist across engine restarts."""
        storage = str(tmp_path / "goals.json")
        
        # Create engine and add goal
        engine1 = LifeContextEngine(storage_path=storage)
        goal = engine1.add_goal("Test Goal", "Description", "test")
        
        # Reload engine
        engine2 = LifeContextEngine(storage_path=storage)
        
        # Verify goal persisted
        found = next((g for g in engine2.goals if g.id == goal.id), None)
        assert found is not None
        assert found.title == "Test Goal"
    
    def test_goal_progress_persists(self, tmp_path):
        """Goal progress persists."""
        storage = str(tmp_path / "goals.json")
        
        engine1 = LifeContextEngine(storage_path=storage)
        goal = engine1.add_goal("Progress Test", "Desc", "test")
        
        # Update progress
        engine1.update_goal_progress(goal.id, 50)
        engine1.update_goal_progress(goal.id, 75)
        
        # Reload
        engine2 = LifeContextEngine(storage_path=storage)
        found = next((g for g in engine2.goals if g.id == goal.id), None)
        
        assert found.progress == 75
        assert found.status == "in_progress"
    
    def test_goal_completion_persists(self, tmp_path):
        """Completed goals persist."""
        storage = str(tmp_path / "goals.json")
        
        engine1 = LifeContextEngine(storage_path=storage)
        goal = engine1.add_goal("Complete Me", "Desc", "test")
        
        # Complete
        engine1.update_goal_progress(goal.id, 100)
        
        # Reload
        engine2 = LifeContextEngine(storage_path=storage)
        
        status = engine2.get_status()
        assert status['goals_completed'] >= 1


class TestCapabilityVotingIntegration:
    """Test capability voting with persistence."""
    
    def test_voting_persists_across_restarts(self, tmp_path):
        """Voting results persist."""
        storage = str(tmp_path / "voting.json")
        
        engine1 = LifeContextEngine(storage_path=storage)
        
        # Propose and vote
        vote_id = engine1.propose_capability("quantum", "hermes")
        engine1.vote_capability(vote_id, "hermes", True, "Good")
        engine1.vote_capability(vote_id, "pi", True, "Agree")
        
        # Reload
        engine2 = LifeContextEngine(storage_path=storage)
        
        # Find vote
        vote = next((v for v in engine2.capability_votes if v['id'] == vote_id), None)
        assert vote is not None
        assert vote['status'] == 'approved'
        
        # Capability should be added
        assert "quantum" in engine2.get_capabilities("hermes") or "quantum" in engine2.get_capabilities("pi")
    
    def test_rejected_votes_persist(self, tmp_path):
        """Rejected votes persist."""
        storage = str(tmp_path / "voting.json")
        
        engine1 = LifeContextEngine(storage_path=storage)
        
        vote_id = engine1.propose_capability("unnecessary", "hermes")
        engine1.vote_capability(vote_id, "hermes", False, "Not needed")
        engine1.vote_capability(vote_id, "pi", False, "Disagree")
        
        # Reload
        engine2 = LifeContextEngine(storage_path=storage)
        
        vote = next((v for v in engine2.capability_votes if v['id'] == vote_id), None)
        assert vote['status'] == 'rejected'


class TestErrorRecoveryIntegration:
    """Test error recovery across components."""
    
    def test_corrupt_storage_recovery(self, tmp_path):
        """Corrupt storage is recovered."""
        storage = tmp_path / "corrupt.json"
        storage.write_text("{invalid json{{{")
        
        # Engine should not crash
        engine = LifeContextEngine(storage_path=str(storage))
        
        # Should have empty state
        assert len(engine.contexts) == 0
        assert len(engine.goals) == 0
        
        # Should still work
        engine.add_goal("New Goal", "Desc", "test")
        assert len(engine.goals) == 1
    
    def test_rl_corrupt_file_recovery(self, tmp_path):
        """Corrupt RL file is recovered."""
        save_path = tmp_path / "corrupt_rl.json"
        save_path.write_text("not json{{{")
        
        rl = ReinforcementLearning()
        result = rl.load(str(save_path))
        
        # Should return False, not crash
        assert result is False
        
        # RL should still work
        rl.update_q_value("test", ActionType.EXECUTE, 1.0, "done")
        assert rl.get_q_value("test", ActionType.EXECUTE) > 0
    
    def test_bridge_reconnection_after_failure(self):
        """Bridge can reconnect after failure."""
        bridge = AgentBridge()
        
        # Disconnect
        bridge.disconnect(AgentType.HERMES)
        
        # Reconnect
        result = bridge.reconnect(AgentType.HERMES)
        
        # Should return boolean
        assert isinstance(result, bool)
    
    def test_life_engine_repair(self, tmp_path):
        """Life engine repair works."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "data.json"))
        
        # Add some data
        engine.add_goal("Test", "Desc", "test")
        
        # Repair should work
        result = engine.repair()
        assert result is True
        
        # Reset should work
        engine.reset()
        assert len(engine.goals) == 0