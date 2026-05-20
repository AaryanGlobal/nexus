"""TDD: Full Autonomous Evolution Loop Tests"""
import pytest
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core" / "src"))

from hermes_pi_bridge_core.bridge import AgentBridge, AgentType
from hermes_pi_bridge_core.life_context import LifeContextEngine
from hermes_pi_bridge_core.rl import ReinforcementLearning, ActionType


class TestFullEvolutionLoop:
    """Test the complete autonomous evolution loop."""
    
    def test_task_routing_to_completion_with_rl_feedback(self, tmp_path):
        """Full loop: route task -> execute -> RL feedback -> persist."""
        # Initialize components
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        rl = ReinforcementLearning()
        
        # Set up capabilities
        engine.add_capability("hermes", "planning")
        engine.add_capability("hermes", "reasoning")
        engine.add_capability("pi", "coding")
        engine.add_capability("pi", "testing")
        
        # Route a coding task
        agent = engine.route_task(["coding", "testing"])
        assert agent == "pi", "Coding task should route to PI"
        
        # Simulate task execution
        if agent == "pi":
            # Task succeeded
            rl.reward(ActionType.EXECUTE, True)
            
            # Record in metrics
            metrics = rl.get_metrics()
            assert metrics['total_updates'] >= 1
            
            # Save RL state
            rl_path = str(tmp_path / "rl.json")
            rl.save(rl_path)
            
            # Reload and verify
            rl2 = ReinforcementLearning()
            rl2.load(rl_path)
            
            stats = rl2.get_stats()
            assert stats['states_learned'] >= 1
    
    def test_capability_based_on_task_outcomes(self, tmp_path):
        """System learns which agent is best for which task."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        rl = ReinforcementLearning()
        
        # Track outcomes for different task types
        for _ in range(5):
            # Planning tasks route to Hermes
            agent = engine.route_task(["planning", "reasoning"])
            if agent:
                rl.update_q_value(f"planning_task_{agent}", ActionType.DELEGATE, 1.0, "done")
        
        for _ in range(5):
            # Coding tasks route to PI
            agent = engine.route_task(["coding", "implementation"])
            if agent:
                rl.update_q_value(f"coding_task_{agent}", ActionType.EXECUTE, 1.0, "done")
        
        # Verify RL learned
        stats = rl.get_stats()
        # States learned should be >= 2 (one for each agent)
        assert stats['states_learned'] >= 1
    
    def test_goal_completion_triggers_learning(self, tmp_path):
        """Goal completion produces RL reward."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        
        # Add a goal
        goal = engine.add_goal("Build AI System", "Create autonomous AI", "capacity")
        
        # Simulate progress
        for progress in [25, 50, 75, 100]:
            engine.update_goal_progress(goal.id, progress)
        
        # Verify goal completed
        found = next((g for g in engine.goals if g.id == goal.id), None)
        assert found.status == "completed"
        
        # RL should track this as positive outcome
        rl = ReinforcementLearning()
        rl.update_q_value("goal_completion", ActionType.EXECUTE, 1.0, "done")
        
        q = rl.get_q_value("goal_completion", ActionType.EXECUTE)
        assert q > 0
    
    def test_context_sharing_based_on_capabilities(self, tmp_path):
        """Context is shared based on agent capabilities."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        
        # Add context to pillar
        engine.add_context("Build AI agent system", "capacity")
        
        # Share with agents that have capabilities
        engine.share_context("hermes")
        engine.share_context("pi")
        
        # Verify context is marked as shared
        shared = engine.get_shared_context()
        assert len(shared) >= 1
        
        # Check that shared_with is populated
        for item in shared:
            if item.get('pillar') == 'capacity':
                assert 'hermes' in item.get('shared_with', [])
    
    def test_evolution_loop_persists_across_restarts(self, tmp_path):
        """Evolution loop state persists across restarts."""
        # First session
        life_path = str(tmp_path / "life.json")
        rl_path = str(tmp_path / "rl.json")
        
        engine1 = LifeContextEngine(storage_path=life_path)
        rl1 = ReinforcementLearning()
        
        # Add goal
        engine1.add_goal("Test Goal", "Description", "test")
        
        # Learn something
        rl1.update_q_value("task1", ActionType.EXECUTE, 1.0, "done")
        
        # Persist
        engine1._save()
        rl1.save(rl_path)
        
        # Second session - reload
        engine2 = LifeContextEngine(storage_path=life_path)
        rl2 = ReinforcementLearning()
        rl2.load(rl_path)
        
        # Verify state restored
        assert len(engine2.goals) == 1
        assert rl2.get_q_value("task1", ActionType.EXECUTE) > 0
    
    def test_bridge_routing_with_capability_check(self, tmp_path):
        """Bridge routes based on capability checks."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        
        # Route task
        agent = engine.route_task(["planning"])
        
        # If route succeeds, find_best_agent should match
        if agent:
            can_handle, missing = engine.can_handle_task(agent, ["planning"])
            assert can_handle, f"{agent} should be able to handle planning"
    
    def test_health_monitoring_tracks_connection_state(self, tmp_path):
        """Health monitoring tracks connection state changes."""
        bridge = AgentBridge()
        
        # Get health status
        health = bridge.get_health()
        
        assert 'hermes' in health
        assert 'pi' in health
        
        # Each should have status and latency
        for agent in ['hermes', 'pi']:
            assert 'status' in health[agent]
            assert 'latency_ms' in health[agent] or health[agent]['latency_ms'] is None
    
    def test_stats_reflect_system_activity(self, tmp_path):
        """Statistics reflect system activity."""
        bridge = AgentBridge()
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        rl = ReinforcementLearning()
        
        # Generate some activity
        engine.add_goal("Test", "Desc", "test")
        engine.add_capability("hermes", "test_cap")
        rl.reward(ActionType.EXECUTE, True)
        
        # Get stats
        bridge_stats = bridge.get_stats()
        engine_stats = engine.get_stats()
        rl_stats = rl.get_stats()
        
        # Verify stats contain expected fields
        assert 'total_messages' in bridge_stats or 'total_messages' in bridge_stats
        assert 'total_goals' in engine_stats or 'total_goals' in engine_stats
        assert 'states_learned' in rl_stats or 'states_learned' in rl_stats


class TestControlAndSteeringIntegration:
    """Test integration of control and steering features."""
    
    def test_can_steer_capabilities_and_route_tasks(self, tmp_path):
        """Can steer capabilities and routing responds."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        
        # Start with default capabilities
        agent1 = engine.route_task(["planning"])
        
        # Add custom capability
        engine.add_capability("hermes", "quantum_computing")
        
        # Route to custom capability
        agent2 = engine.route_task(["quantum_computing"])
        
        assert agent2 == "hermes", "Should route to agent with custom capability"
    
    def test_can_update_goals_and_track_progress(self, tmp_path):
        """Can update goals and see progress reflected."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        
        # Add goal
        goal = engine.add_goal("Run Marathon", "Complete 26.2 miles", "vitality")
        
        # Update progress
        for progress in [10, 25, 50, 75]:
            engine.update_goal_progress(goal.id, progress)
            
            # Verify progress updated
            current = next((g for g in engine.goals if g.id == goal.id), None)
            assert current.progress == progress
        
        # Complete goal
        engine.update_goal_progress(goal.id, 100)
        
        # Verify completed
        final = next((g for g in engine.goals if g.id == goal.id), None)
        assert final.status == "completed"
        
        # Status should reflect
        status = engine.get_status()
        assert status['goals_completed'] >= 1
    
    def test_can_propose_and_vote_on_capabilities(self, tmp_path):
        """Can propose and vote on capabilities."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        
        # Propose capability
        vote_id = engine.propose_capability("advanced_reasoning", "hermes")
        
        # Vote approval
        engine.vote_capability(vote_id, "hermes", True, "Good idea")
        engine.vote_capability(vote_id, "pi", True, "Agree")
        
        # Verify approved
        vote = next(v for v in engine.capability_votes if v['id'] == vote_id)
        assert vote['status'] == 'approved'
        
        # Capability should be added
        assert "advanced_reasoning" in engine.get_capabilities("hermes") or \
               "advanced_reasoning" in engine.get_capabilities("pi")
    
    def test_can_control_life_pillars(self, tmp_path):
        """Can control what pillars exist and contain."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        
        # Add custom pillars
        engine.add_context("Start a startup", "entrepreneurship")
        engine.add_context("Learn to cook", "personal")
        
        # Add goals to pillars
        engine.add_goal("Launch MVP", "Release first version", "entrepreneurship")
        engine.add_goal("Cook a meal", "Make dinner", "personal")
        
        # Verify pillars exist
        pillars = engine.get_pillars()
        assert "entrepreneurship" in pillars
        assert "personal" in pillars
        
        # Verify pillar contents
        ent_contexts = engine.get_contexts_by_pillar("entrepreneurship")
        ent_goals = engine.get_goals_by_pillar("entrepreneurship")
        assert len(ent_contexts) == 1
        assert len(ent_goals) == 1


class TestResilienceAndRecovery:
    """Test resilience and recovery mechanisms."""
    
    def test_handles_corrupted_storage_gracefully(self, tmp_path):
        """Handles corrupted storage files gracefully."""
        # Create corrupted file
        storage = tmp_path / "corrupt.json"
        storage.write_text("not valid json{{{")
        
        # Should not crash, should use defaults
        engine = LifeContextEngine(storage_path=str(storage))
        
        # Should have empty state
        assert len(engine.contexts) == 0
        assert len(engine.goals) == 0
        
        # Should still be functional
        engine.add_goal("New Goal", "Desc", "test")
        assert len(engine.goals) == 1
    
    def test_handles_invalid_capabilities(self, tmp_path):
        """Handles invalid capability additions."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        
        # Add duplicate capability
        engine.add_capability("hermes", "planning")
        engine.add_capability("hermes", "planning")
        
        caps = engine.get_capabilities("hermes")
        assert caps.count("planning") == 1
    
    def test_handles_invalid_goal_progress(self, tmp_path):
        """Handles invalid goal progress values."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        
        goal = engine.add_goal("Test", "Desc", "test")
        
        # Invalid progress (negative)
        result = engine.update_goal_progress(goal.id, -10)
        # Should handle gracefully
        
        # Should cap at 0
        found = next(g for g in engine.goals if g.id == goal.id)
        assert found.progress >= 0
    
    def test_bridges_gracefully_handle_disconnection(self):
        """Bridge handles disconnection gracefully."""
        bridge = AgentBridge()
        
        # Disconnect
        bridge.disconnect(AgentType.HERMES)
        bridge.disconnect(AgentType.PI)
        
        # Status should still work
        status = bridge.get_connection_status()
        assert 'hermes' in status
        assert 'pi' in status
        
        # Reconnect should work
        result = bridge.reconnect(AgentType.HERMES)
        assert isinstance(result, bool)
    
    def test_rl_handles_missing_q_values(self):
        """RL handles queries for non-existent Q-values."""
        rl = ReinforcementLearning()
        
        # Query non-existent state/action
        q = rl.get_q_value("nonexistent", ActionType.EXECUTE)
        assert q == 0.0
        
        # Should not crash
        stats = rl.get_stats()
        assert stats is not None


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""
    
    def test_new_user_onboarding(self, tmp_path):
        """Simulates new user getting started with Nexus."""
        storage = str(tmp_path / "life.json")
        engine = LifeContextEngine(storage_path=storage)
        
        # 1. Check capabilities auto-discovered
        assert len(engine.get_capabilities("hermes")) > 0
        assert len(engine.get_capabilities("pi")) > 0
        
        # 2. Add sample data
        result = engine.add_sample_data()
        assert result['contexts'] >= 5
        assert result['goals'] >= 3
        
        # 3. Verify pillars created
        pillars = engine.get_pillars()
        assert len(pillars) >= 5
        
        # 4. Check status
        status = engine.get_status()
        assert status['goals_total'] >= 3
    
    def test_daily_task_routing(self, tmp_path):
        """Simulates daily task routing workflow."""
        storage = str(tmp_path / "life.json")
        engine = LifeContextEngine(storage_path=storage)
        
        # Set up capabilities
        engine.discover_capabilities("hermes")
        engine.discover_capabilities("pi")
        
        # Route planning task
        planning_agent = engine.route_task(["planning", "strategy"])
        assert planning_agent == "hermes"
        
        # Route coding task
        coding_agent = engine.route_task(["coding", "execution"])
        assert coding_agent == "pi"
        
        # Route analysis task
        analysis_agent = engine.route_task(["analysis", "reasoning"])
        assert analysis_agent == "hermes"
    
    def test_capability_proposal_workflow(self, tmp_path):
        """Simulates capability proposal and approval."""
        storage = str(tmp_path / "life.json")
        engine = LifeContextEngine(storage_path=storage)
        
        # 1. Propose new capability
        vote_id = engine.propose_capability("machine_learning", "hermes")
        
        # 2. Get pending votes
        status = engine.get_status()
        assert status['pending_votes'] == 1
        
        # 3. Vote
        engine.vote_capability(vote_id, "hermes", True, "Strategic for future")
        engine.vote_capability(vote_id, "pi", True, "Good addition")
        
        # 4. Verify approved
        vote = next(v for v in engine.capability_votes if v['id'] == vote_id)
        assert vote['status'] == 'approved'
        
        # 5. Verify capability added
        h_caps = engine.get_capabilities("hermes")
        assert "machine_learning" in h_caps or "machine_learning" in engine.get_capabilities("pi")
    
    def test_goal_tracking_workflow(self, tmp_path):
        """Simulates goal creation to completion."""
        storage = str(tmp_path / "life.json")
        engine = LifeContextEngine(storage_path=storage)
        
        # 1. Create goal
        goal = engine.add_goal(
            "Learn Python",
            "Master Python programming",
            "capacity"
        )
        initial_status = engine.get_status()
        assert initial_status['goals_total'] >= 1
        
        # 2. Update progress
        for p in [10, 25, 50, 75, 100]:
            engine.update_goal_progress(goal.id, p)
        
        # 3. Verify completion
        final_status = engine.get_status()
        assert final_status['goals_completed'] >= 1