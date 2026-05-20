"""TDD: RL Persistence and Learning Continuity Tests"""
import pytest
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core" / "src"))

from hermes_pi_bridge_core.rl import RLConfig, ActionType, ReinforcementLearning
from hermes_pi_bridge_core.persistence import PersistenceManager
from hermes_pi_bridge_core.life_context import LifeContextEngine


class TestRLPersistence:
    """Test RL persistence to disk."""
    
    def test_rl_persists_q_values(self, tmp_path):
        """RL Q-values persist to storage."""
        storage = str(tmp_path / "rl.json")
        rl = ReinforcementLearning()
        
        # Learn something
        rl.update_q_value("task1", ActionType.EXECUTE, 1.0, "complete")
        rl.update_q_value("task2", ActionType.DELEGATE, 0.5, "complete")
        
        # Save
        data = {
            "q_table": {
                state: {
                    action.value: {"value": qv.value, "count": qv.count}
                    for action, qv in actions.items()
                }
                for state, actions in rl.q_table.items()
            },
            "total_rewards": rl.total_rewards,
            "total_punishments": rl.total_punishments
        }
        
        with open(storage, 'w') as f:
            json.dump(data, f)
        
        # Reload
        with open(storage) as f:
            loaded = json.load(f)
        
        assert "task1" in loaded["q_table"]
        assert "task2" in loaded["q_table"]
    
    def test_rl_reloads_q_values(self, tmp_path):
        """RL can reload Q-values from storage."""
        storage = str(tmp_path / "rl.json")
        
        # Create and save
        rl1 = ReinforcementLearning()
        for i in range(5):
            rl1.update_q_value("coding", ActionType.EXECUTE, 1.0, "complete")
        
        q_before = rl1.get_q_value("coding", ActionType.EXECUTE)
        
        # Save to file
        save_data = {
            "q_table": {},
            "total_rewards": rl1.total_rewards,
            "total_punishments": rl1.total_punishments
        }
        for state, actions in rl1.q_table.items():
            save_data["q_table"][state] = {
                action.value: {"value": qv.value, "count": qv.count}
                for action, qv in actions.items()
            }
        
        with open(storage, 'w') as f:
            json.dump(save_data, f)
        
        # Reload into new instance
        rl2 = ReinforcementLearning()
        if Path(storage).exists():
            with open(storage) as f:
                loaded = json.load(f)
            for state, actions in loaded.get("q_table", {}).items():
                rl2.q_table[state] = {}
                for action_val, qv_data in actions.items():
                    action = ActionType(action_val)
                    from hermes_pi_bridge_core.rl import QValue
                    rl2.q_table[state][action] = QValue(action=action, value=qv_data["value"], count=qv_data["count"])
        
        q_after = rl2.get_q_value("coding", ActionType.EXECUTE)
        assert q_after is not None


class TestTaskRouting:
    """Test automatic task routing based on capabilities."""
    
    def test_can_route_task_by_capability(self):
        """Can route task to agent with matching capability."""
        from hermes_pi_bridge_core.life_context import LifeContextEngine
        
        engine = LifeContextEngine()
        engine.add_capability("hermes", "planning")
        engine.add_capability("hermes", "strategy")
        engine.add_capability("pi", "coding")
        engine.add_capability("pi", "execution")
        
        # Check which agent can handle
        can_do_hermes, missing = engine.can_handle_task("hermes", ["planning"])
        can_do_pi, missing_pi = engine.can_handle_task("pi", ["coding"])
        
        assert can_do_hermes is True
        assert can_do_pi is True
        
        # Test routing
        if engine.can_handle_task("hermes", ["planning"])[0]:
            route_to = "hermes"
        elif engine.can_handle_task("pi", ["planning"])[0]:
            route_to = "pi"
        else:
            route_to = "unknown"
        
        assert route_to == "hermes"
    
    def test_can_detect_best_agent_for_task(self):
        """Can find best agent for a task."""
        from hermes_pi_bridge_core.life_context import LifeContextEngine
        
        engine = LifeContextEngine()
        
        # Both have some capabilities
        engine.add_capability("hermes", "planning")
        engine.add_capability("hermes", "reasoning")
        engine.add_capability("pi", "coding")
        engine.add_capability("pi", "testing")
        
        # Find best for planning
        def find_best_agent(task_reqs):
            candidates = []
            for agent in ["hermes", "pi"]:
                can_do, missing = engine.can_handle_task(agent, task_reqs)
                if can_do:
                    candidates.append(agent)
            return candidates[0] if candidates else None
        
        best = find_best_agent(["planning"])
        assert best == "hermes"
        
        best = find_best_agent(["coding"])
        assert best == "pi"


class TestSelfEvolutionContinuity:
    """Test self-evolution continues across sessions."""
    
    def test_life_context_persists_across_restarts(self, tmp_path):
        """Life context persists across restarts."""
        storage = str(tmp_path / "life.json")
        
        # Create engine and add data
        engine1 = LifeContextEngine(storage_path=storage)
        engine1.add_context("Important goal", "career")
        engine1.add_goal("Build AI system", "Create autonomous AI", "capacity")
        
        # Reload
        engine2 = LifeContextEngine(storage_path=storage)
        
        assert len(engine2.contexts) == 1
        assert len(engine2.goals) == 1
    
    def test_capabilities_persist_across_restarts(self, tmp_path):
        """Capabilities persist across restarts."""
        storage = str(tmp_path / "life.json")
        
        engine1 = LifeContextEngine(storage_path=storage)
        engine1.add_capability("hermes", "custom_skill")
        engine1.add_capability("pi", "custom_skill")
        
        # Reload
        engine2 = LifeContextEngine(storage_path=storage)
        
        assert "custom_skill" in engine2.get_capabilities("hermes")
        assert "custom_skill" in engine2.get_capabilities("pi")
    
    def test_goal_progress_persists(self, tmp_path):
        """Goal progress persists."""
        storage = str(tmp_path / "life.json")
        
        engine1 = LifeContextEngine(storage_path=storage)
        goal = engine1.add_goal("Test", "Description", "test")
        engine1.update_goal_progress(goal.id, 50)
        
        # Reload
        engine2 = LifeContextEngine(storage_path=storage)
        found_goal = next((g for g in engine2.goals if g.id == goal.id), None)
        
        assert found_goal is not None
        assert found_goal.progress == 50
        assert found_goal.status == "in_progress"


class TestNexusFullLifecycle:
    """Test full Nexus lifecycle."""
    
    def test_can_add_goal_and_track_to_completion(self, tmp_path):
        """Full lifecycle: add goal -> track progress -> complete."""
        storage = str(tmp_path / "life.json")
        engine = LifeContextEngine(storage_path=storage)
        
        # Add goal
        goal = engine.add_goal("Run Marathon", "Complete 26.2 miles", "vitality")
        assert goal.status == "not_started"
        
        # Track progress
        for progress in [25, 50, 75, 100]:
            engine.update_goal_progress(goal.id, progress)
        
        # Verify completed
        found = next((g for g in engine.goals if g.id == goal.id), None)
        assert found.status == "completed"
        assert found.completed_at is not None
        
        # Status should reflect
        status = engine.get_status()
        assert status["goals_completed"] == 1
    
    def test_can_propose_and_approve_capability(self, tmp_path):
        """Full lifecycle: propose capability -> vote -> approve."""
        storage = str(tmp_path / "life.json")
        engine = LifeContextEngine(storage_path=storage)
        
        # Propose
        vote_id = engine.propose_capability("quantum_computing", "hermes")
        
        # Vote
        engine.vote_capability(vote_id, "hermes", True, "Great idea")
        engine.vote_capability(vote_id, "pi", True, "Interesting")
        
        # Check approved
        vote = next(v for v in engine.capability_votes if v["id"] == vote_id)
        assert vote["status"] == "approved"
        
        # Capability should be added
        assert "quantum_computing" in engine.get_capabilities("hermes") or "quantum_computing" in engine.get_capabilities("pi")
    
    def test_can_create_pillar_and_add_context(self, tmp_path):
        """Full lifecycle: create pillar -> add context -> add goal."""
        storage = str(tmp_path / "life.json")
        engine = LifeContextEngine(storage_path=storage)
        
        # Add context to new pillar
        engine.add_context("Master machine learning", "ai_mastery")
        
        # Add goal to same pillar
        goal = engine.add_goal("Complete ML course", "Finish online course", "ai_mastery")
        
        # Verify
        pillars = engine.get_pillars()
        assert "ai_mastery" in pillars
        
        contexts = engine.get_contexts_by_pillar("ai_mastery")
        assert len(contexts) == 1
        
        goals = engine.get_goals_by_pillar("ai_mastery")
        assert len(goals) == 1


class TestControlAndSteering:
    """Test ability to control and steer the system."""
    
    def test_can_control_life_pillars(self, tmp_path):
        """Can control what pillars exist."""
        storage = str(tmp_path / "life.json")
        engine = LifeContextEngine(storage_path=storage)
        
        # Add custom pillars
        engine.add_context("Work on startups", "entrepreneurship")
        engine.add_context("Learn new skills", "entrepreneurship")
        engine.add_context("Build relationships", "social")
        
        pillars = engine.get_pillars()
        
        assert "entrepreneurship" in pillars
        assert "social" in pillars
        assert len(pillars) >= 2
    
    def test_can_steer_capabilities(self, tmp_path):
        """Can steer what capabilities agents have."""
        storage = str(tmp_path / "life.json")
        engine = LifeContextEngine(storage_path=storage)
        
        # Add custom capabilities
        engine.add_capability("hermes", "strategic_thinking")
        engine.add_capability("hermes", "risk_management")
        engine.add_capability("pi", "code_review")
        engine.add_capability("pi", "deployment_automation")
        
        h_caps = engine.get_capabilities("hermes")
        p_caps = engine.get_capabilities("pi")
        
        assert "strategic_thinking" in h_caps
        assert "risk_management" in h_caps
        assert "code_review" in p_caps
        assert "deployment_automation" in p_caps
    
    def test_can_update_goals(self, tmp_path):
        """Can update and steer goals."""
        storage = str(tmp_path / "life.json")
        engine = LifeContextEngine(storage_path=storage)
        
        goal1 = engine.add_goal("Learn Python", "Master Python", "capacity")
        goal2 = engine.add_goal("Run 5K", "Complete 5K run", "vitality")
        
        # Update progress
        engine.update_goal_progress(goal1.id, 75)
        engine.update_goal_progress(goal2.id, 50)
        
        # Verify
        g1 = next((g for g in engine.goals if g.id == goal1.id), None)
        g2 = next((g for g in engine.goals if g.id == goal2.id), None)
        
        assert g1.progress == 75
        assert g2.progress == 50
    
    def test_can_query_system_state(self, tmp_path):
        """Can query full system state."""
        storage = str(tmp_path / "life.json")
        engine = LifeContextEngine(storage_path=storage)
        
        # Add some data
        engine.add_context("Test context", "test")
        engine.add_goal("Test goal", "Desc", "test")
        engine.add_capability("hermes", "test_cap")
        
        # Query
        status = engine.get_status()
        config_status = engine.get_status()  # Same for now
        
        assert "pillars" in status
        assert "goals_total" in status
        assert "goals_completed" in status
        assert "capabilities" in status