"""TDD: Nexus Agent End-to-End Tests"""
import pytest
import tempfile
import sys
from pathlib import Path

# Add nexus to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core" / "src"))

from hermes_pi_bridge_core.autonomous import AutonomousNHIL, AutonomousConfig


class TestNexusAgent:
    """Test agent directly."""
    
    def test_agent_starts_and_stops(self):
        """Agent should start and stop cleanly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = f"{tmpdir}/state.json"
            agent = AutonomousNHIL(AutonomousConfig(storage_path=config_path))
            agent.start()
            assert agent.running
            agent.stop()
            assert not agent.running
    
    def test_ideation_creates_goals(self):
        """Ideation should create goals."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = f"{tmpdir}/state.json"
            agent = AutonomousNHIL(AutonomousConfig(storage_path=config_path))
            agent.start()
            
            goals = agent.add_ideation("[TEST] Test goal")
            assert len(goals) >= 1
            assert "Test goal" in agent.goals.goals[0].title
            
            agent.stop()
    
    def test_work_on_goal(self):
        """Work on goal should update status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = f"{tmpdir}/state.json"
            agent = AutonomousNHIL(AutonomousConfig(storage_path=config_path))
            agent.start()
            
            agent.add_ideation("[TEST] Work goal")
            result = agent.work_on_goal()
            
            assert result.get('success') == True
            assert agent.goals.current_goal is not None
            
            agent.stop()
    
    def test_governance_validation(self):
        """Governance should validate decisions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = f"{tmpdir}/state.json"
            agent = AutonomousNHIL(AutonomousConfig(storage_path=config_path))
            agent.start()
            
            result = agent.validate_action('execute', 'Test task', {})
            assert 'confidence' in result
            assert 'should_proceed' in result
            
            agent.stop()
    
    def test_rl_reward(self):
        """RL should track rewards."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = f"{tmpdir}/state.json"
            agent = AutonomousNHIL(AutonomousConfig(storage_path=config_path))
            agent.start()
            
            reward = agent.apply_reward('execute', success=True)
            assert reward > 0
            
            agent.stop()
    
    def test_persistence_survives_restart(self):
        """State should survive restart."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a shared path for both agents
            goals_path = f"{tmpdir}/goals.json"
            
            # Create agent, add goals
            agent1 = AutonomousNHIL(AutonomousConfig(storage_path=f"{tmpdir}/state1.json"))
            # Override goals path to be in temp dir
            agent1.goals.storage_path = goals_path
            agent1.start()
            
            # Add ideation (creates goals)
            goals_before = len(agent1.goals.goals)
            agent1.add_ideation("[TEST] Persistent goal")
            goals_after = len(agent1.goals.goals)
            
            assert goals_after > goals_before, f"Expected goals to increase: {goals_before} -> {goals_after}"
            
            agent1.stop()
            
            # Verify goals file was created
            import os
            assert os.path.exists(goals_path), f"Goals file should exist at {goals_path}"
            
            # Restart agent with same goals path
            agent2 = AutonomousNHIL(AutonomousConfig(storage_path=f"{tmpdir}/state2.json"))
            agent2.goals.storage_path = goals_path
            agent2.goals._load_goals()  # Reload from new path
            
            # Goals should be loaded from file
            assert len(agent2.goals.goals) >= 1, f"Goals should persist: got {len(agent2.goals.goals)}"
    
    def test_full_user_journey(self):
        """Test complete user journey."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = f"{tmpdir}/state.json"
            goals_path = f"{tmpdir}/journey_goals.json"
            
            agent = AutonomousNHIL(AutonomousConfig(storage_path=config_path))
            agent.goals.storage_path = goals_path  # Use clean path
            agent.start()
            
            # Get initial count
            initial_count = len(agent.goals.goals)
            
            # 1. Add ideation
            goals = agent.add_ideation("[HIGH] Learn Rust\n[CRITICAL] Get promoted")
            
            # Count should increase by 2
            assert len(agent.goals.goals) == initial_count + 2
            
            # 2. Get suggestions
            suggestions = agent.get_suggestions()
            assert len(suggestions) > 0
            
            # 3. Work on goal
            goal = agent.work_on_goal()
            assert goal.get('success')
            
            # 4. Do some work
            result = agent.inject_task("echo 'Working on goal'")
            assert result.get('success')
            
            # 5. Update progress
            agent.update_goal_progress(goal['goal_id'], 1.0)
            
            # 6. Check governance
            gov = agent.get_governance_status()
            assert 'circuit_open' in gov
            
            # 7. Check RL
            rl = agent.get_rl_statistics()
            assert 'total_rewards' in rl
            
            agent.stop()
            
            print("✅ Full user journey completed successfully")
    
    def test_tdd_cycle(self):
        """TDD cycle should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = f"{tmpdir}/state.json"
            agent = AutonomousNHIL(AutonomousConfig(storage_path=config_path))
            agent.start()
            
            result = agent.run_tdd_cycle(
                "assert 1 == 2",  # Failing test
                "x = 1"            # Fix
            )
            
            assert result is not None
            assert 'phase' in result
            
            agent.stop()
    
    def test_audit_trail(self):
        """Audit trail should track actions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = f"{tmpdir}/state.json"
            agent = AutonomousNHIL(AutonomousConfig(storage_path=config_path))
            agent.start()
            
            agent.inject_task("echo test")
            agent.add_ideation("[TEST] Audit test")
            
            log = agent.get_audit_log()
            assert len(log) >= 2
            
            agent.stop()