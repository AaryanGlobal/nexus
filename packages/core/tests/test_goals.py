"""TDD: Goal-oriented system tests"""
import pytest
import tempfile
from hermes_pi_bridge_core.goals import GoalManager, Goal, GoalStatus, GoalPriority


class TestGoalCreation:
    """Test goal creation from ideation."""
    
    def test_add_goal(self):
        gm = GoalManager()
        goal = gm.add_goal("Learn Rust", "Master Rust programming")
        assert goal.title == "Learn Rust"
        assert goal.status == GoalStatus.ACTIVE
    
    def test_add_ideation(self):
        gm = GoalManager()
        content = """
        [CRITICAL] Get promoted to senior
        [HIGH] Learn machine learning
        Write more tests
        """
        goals = gm.add_ideation(content)
        assert len(goals) >= 2
    
    def test_goal_persists(self, tmp_path):
        path = str(tmp_path / "goals.json")
        gm1 = GoalManager(storage_path=path)
        gm1.add_goal("Test goal", "A test")
        
        gm2 = GoalManager(storage_path=path)
        assert len(gm2.goals) == 1
        assert gm2.goals[0].title == "Test goal"


class TestGoalTracking:
    """Test working toward goals."""
    
    def test_get_next_goal(self):
        gm = GoalManager()
        gm.add_goal("Low priority task", "desc")
        gm.add_goal("HIGH priority work", "desc")
        
        next_goal = gm.get_next_goal()
        assert next_goal is not None
    
    def test_work_on_goal(self):
        gm = GoalManager()
        goal = gm.add_goal("Test goal", "A test")
        
        result = gm.work_on_goal(goal.id)
        assert result.status == GoalStatus.IN_PROGRESS
        assert gm.current_goal.id == goal.id
    
    def test_update_progress(self):
        gm = GoalManager()
        goal = gm.add_goal("Test goal", "A test")
        
        gm.update_goal_progress(goal.id, 0.5)
        assert goal.progress == 0.5
        
        gm.update_goal_progress(goal.id, 1.0)
        assert goal.progress == 1.0
        assert goal.status == GoalStatus.COMPLETED


class TestSuggestions:
    """Test suggestion generation."""
    
    def test_suggestions_from_goals(self):
        gm = GoalManager()
        gm.add_goal("Goal 1", "desc")
        gm.add_goal("Goal 2", "desc")
        
        suggestions = gm.generate_suggestions()
        assert len(suggestions) > 0
    
    def test_suggestions_not_empty(self):
        gm = GoalManager()
        goal = gm.add_goal("Study AI", "Learn machine learning")
        gm.work_on_goal(goal.id)
        
        suggestions = gm.generate_suggestions()
        assert len(suggestions) > 0