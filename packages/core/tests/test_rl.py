"""TDD: Reinforcement Learning Tests"""
import pytest
from hermes_pi_bridge_core.rl import (
    ReinforcementLearning, RLConfig, ActionType, Experience
)


class TestQValues:
    """Test Q-value management."""
    
    def test_initial_q_value_is_zero(self):
        """Initial Q-value should be zero."""
        rl = ReinforcementLearning()
        q = rl.get_q_value("state1", ActionType.EXECUTE)
        assert q == 0.0
    
    def test_update_q_value(self):
        """Q-values should update correctly."""
        rl = ReinforcementLearning()
        
        new_q = rl.update_q_value("state1", ActionType.EXECUTE, 1.0, "state2")
        assert new_q > 0.0
    
    def test_q_value_converges(self):
        """Q-values should converge with enough updates."""
        rl = ReinforcementLearning()
        
        for _ in range(100):
            rl.update_q_value("state1", ActionType.EXECUTE, 1.0, "state2")
        
        q = rl.get_q_value("state1", ActionType.EXECUTE)
        assert q > 0.5


class TestActionSelection:
    """Test action selection."""
    
    def test_select_action_returns_valid_action(self):
        """Should return valid action type."""
        rl = ReinforcementLearning()
        action, confidence = rl.select_action("state1")
        assert isinstance(action, ActionType)
        assert 0 <= confidence <= 1.0
    
    def test_exploration_rate(self):
        """Exploration should happen sometimes."""
        rl = ReinforcementLearning()
        rl.config.exploration_rate = 1.0  # Always explore
        
        actions = set()
        for _ in range(20):
            action, _ = rl.select_action("state1")
            actions.add(action)
        
        # Should get multiple different actions
        assert len(actions) > 1
    
    def test_exploitation_selects_best(self):
        """Should select best known action."""
        rl = ReinforcementLearning()
        rl.config.exploration_rate = 0.0  # Never explore
        
        # Train: execute is best for state1
        for _ in range(50):
            rl.update_q_value("state1", ActionType.EXECUTE, 2.0, "end")
            rl.update_q_value("state1", ActionType.DELEGATE, 0.5, "end")
        
        action, _ = rl.select_action("state1")
        assert action == ActionType.EXECUTE


class TestRewards:
    """Test reward/punishment system."""
    
    def test_positive_reward(self):
        """Positive action should get reward."""
        rl = ReinforcementLearning()
        reward = rl.reward(ActionType.EXECUTE, success=True)
        assert reward > 0
        assert rl.total_rewards > 0
    
    def test_negative_reward_punishment(self):
        """Failed action should get punishment."""
        rl = ReinforcementLearning()
        reward = rl.reward(ActionType.EXECUTE, success=False)
        assert reward < 0
        assert rl.total_punishments > 0
    
    def test_reward_updates_q_value(self):
        """Reward should update Q-value."""
        rl = ReinforcementLearning()
        
        initial_q = rl.get_q_value("test_state", ActionType.EXECUTE)
        rl.reward(ActionType.EXECUTE, success=True, context="test_state")
        new_q = rl.get_q_value("test_state", ActionType.EXECUTE)
        
        assert new_q > initial_q
    
    def test_efficiency_bonus(self):
        """Efficient actions should get bonus."""
        rl = ReinforcementLearning()
        
        reward_normal = rl.reward(ActionType.EXECUTE, success=True, efficiency=0)
        reward_efficient = rl.reward(ActionType.EXECUTE, success=True, efficiency=5)
        
        assert reward_efficient > reward_normal


class TestStatistics:
    """Test learning statistics."""
    
    def test_statistics_tracked(self):
        """Statistics should be tracked."""
        rl = ReinforcementLearning()
        
        rl.reward(ActionType.EXECUTE, success=True)
        rl.reward(ActionType.DELEGATE, success=False)
        
        stats = rl.get_statistics()
        
        assert 'total_rewards' in stats
        assert 'total_punishments' in stats
        assert 'actions_taken' in stats
        # Check that actions are tracked (may be int or enum key)
        assert sum(stats['actions_taken'].values()) >= 2
    
    def test_success_rate_calculated(self):
        """Success rate should be calculated."""
        rl = ReinforcementLearning()
        
        # 3 successes, 1 failure
        for _ in range(3):
            rl.reward(ActionType.EXECUTE, success=True)
        rl.reward(ActionType.EXECUTE, success=False)
        
        stats = rl.get_statistics()
        rate = stats['success_rate'][ActionType.EXECUTE.value]
        assert 0.5 < rate <= 1.0


class TestPolicy:
    """Test policy management."""
    
    def test_get_policy(self):
        """Should get policy for state."""
        rl = ReinforcementLearning()
        
        # Train
        for _ in range(10):
            rl.reward(ActionType.EXECUTE, success=True, context="trained_state")
        
        policy = rl.get_policy("trained_state")
        
        assert 'action' in policy
        assert 'confidence' in policy
        assert 'q_values' in policy
    
    def test_unknown_state_policy(self):
        """Unknown state should have empty policy."""
        rl = ReinforcementLearning()
        policy = rl.get_policy("unknown_state")
        
        assert policy['action'] is None
        assert policy['confidence'] == 0.0


class TestExploration:
    """Test exploration adjustment."""
    
    def test_adjust_exploration_up(self):
        """Should increase exploration on failure."""
        rl = ReinforcementLearning()
        rl.config.exploration_rate = 0.1
        
        rl.adjust_exploration(0.3)  # Low success rate
        
        assert rl.config.exploration_rate > 0.1
    
    def test_adjust_exploration_down(self):
        """Should decrease exploration on success."""
        rl = ReinforcementLearning()
        rl.config.exploration_rate = 0.2
        
        rl.adjust_exploration(0.95)  # High success rate
        
        assert rl.config.exploration_rate < 0.2


class TestIntegration:
    """Test RL integration with agent."""
    
    def test_confidence_calculated(self):
        """Confidence should be calculable."""
        rl = ReinforcementLearning()
        
        # Add more history for higher confidence
        for _ in range(15):
            rl.reward(ActionType.EXECUTE, success=True, context="state1")
        
        action, confidence = rl.select_action("state1")
        
        assert confidence >= 0.5  # Should have some confidence
    
    def test_multiple_states(self):
        """Should learn different states differently."""
        rl = ReinforcementLearning()
        
        # State1: execute is best (give more reward)
        for _ in range(30):
            rl.update_q_value("state1", ActionType.EXECUTE, 2.0, "end")
            rl.update_q_value("state1", ActionType.DELEGATE, -0.5, "end")
        
        # State2: delegate is best (give more reward)
        for _ in range(30):
            rl.update_q_value("state2", ActionType.DELEGATE, 2.0, "end")
            rl.update_q_value("state2", ActionType.EXECUTE, -0.5, "end")
        
        action1, _ = rl.select_action("state1")
        action2, _ = rl.select_action("state2")
        
        # With significant reward difference, should prefer different actions
        q1_execute = rl.get_q_value("state1", ActionType.EXECUTE)
        q1_delegate = rl.get_q_value("state1", ActionType.DELEGATE)
        q2_execute = rl.get_q_value("state2", ActionType.EXECUTE)
        q2_delegate = rl.get_q_value("state2", ActionType.DELEGATE)
        
        # For state1, execute should have higher Q
        assert q1_execute > q1_delegate
        # For state2, delegate should have higher Q
        assert q2_delegate > q2_execute


class TestReset:
    """Test RL reset."""
    
    def test_reset_clears_all(self):
        """Reset should clear all learning."""
        rl = ReinforcementLearning()
        
        rl.reward(ActionType.EXECUTE, success=True, context="test")
        
        rl.reset()
        
        stats = rl.get_statistics()
        assert stats['states_learned'] == 0
        assert stats['experiences'] == 0
        assert stats['total_rewards'] == 0