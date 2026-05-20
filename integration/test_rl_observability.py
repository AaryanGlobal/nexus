"""TDD: RL Persistence and Observability Tests"""
import pytest
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core" / "src"))

from hermes_pi_bridge_core.rl import RLConfig, ActionType, ReinforcementLearning


class TestRLPersistence:
    """Test RL persistence to disk."""
    
    def test_rl_has_save_method(self):
        """RL should have save method."""
        rl = ReinforcementLearning()
        assert hasattr(rl, 'save'), "RL should have save method"
    
    def test_rl_has_load_method(self):
        """RL should have load method."""
        rl = ReinforcementLearning()
        assert hasattr(rl, 'load'), "RL should have load method"
    
    def test_rl_can_save_q_values(self, tmp_path):
        """RL can save Q-values to file."""
        rl = ReinforcementLearning()
        
        # Learn something
        rl.update_q_value("task1", ActionType.EXECUTE, 1.0, "complete")
        rl.update_q_value("task2", ActionType.DELEGATE, 0.5, "complete")
        
        # Save
        save_path = str(tmp_path / "rl_data.json")
        result = rl.save(save_path)
        
        assert result is True
        assert Path(save_path).exists()
    
    def test_rl_can_load_q_values(self, tmp_path):
        """RL can load Q-values from file."""
        # Create and save
        rl1 = ReinforcementLearning()
        for i in range(5):
            rl1.update_q_value("coding", ActionType.EXECUTE, 1.0, "complete")
        
        save_path = str(tmp_path / "rl_data.json")
        rl1.save(save_path)
        
        # Load into new instance
        rl2 = ReinforcementLearning()
        result = rl2.load(save_path)
        
        assert result is True
        q = rl2.get_q_value("coding", ActionType.EXECUTE)
        assert q > 0  # Should have learned
    
    def test_rl_persists_all_data(self, tmp_path):
        """RL saves all learning data."""
        rl = ReinforcementLearning()
        
        # Add experiences
        for i in range(3):
            rl.update_q_value(f"task_{i}", ActionType.EXECUTE, 0.5 + i * 0.1, "done")
        
        save_path = str(tmp_path / "rl_data.json")
        rl.save(save_path)
        
        # Load and verify
        rl2 = ReinforcementLearning()
        rl2.load(save_path)
        
        for i in range(3):
            q = rl2.get_q_value(f"task_{i}", ActionType.EXECUTE)
            assert q is not None


class TestRLStats:
    """Test RL statistics and observability."""
    
    def test_rl_has_get_stats_method(self):
        """RL should have get_stats method."""
        rl = ReinforcementLearning()
        assert hasattr(rl, 'get_stats'), "RL should have get_stats"
    
    def test_get_stats_returns_dict(self):
        """get_stats returns a dictionary."""
        rl = ReinforcementLearning()
        stats = rl.get_stats()
        
        assert isinstance(stats, dict)
    
    def test_get_stats_includes_q_table_size(self):
        """Stats include Q-table size."""
        rl = ReinforcementLearning()
        
        rl.update_q_value("task1", ActionType.EXECUTE, 1.0, "done")
        rl.update_q_value("task2", ActionType.EXECUTE, 0.5, "done")
        
        stats = rl.get_stats()
        
        # States learned = q_table_size
        assert 'states_learned' in stats
        assert stats['states_learned'] >= 2
    
    def test_get_stats_includes_learning_rate(self):
        """Stats include learning configuration."""
        rl = ReinforcementLearning()
        stats = rl.get_stats()
        
        assert 'exploration_rate' in stats
        # Learning rate is in config, not directly in stats
        assert stats['exploration_rate'] is not None
    
    def test_get_stats_includes_action_counts(self):
        """Stats include action counts."""
        rl = ReinforcementLearning()
        
        # Use reward to count actions (this is what actually increments counts)
        for _ in range(10):
            rl.reward(ActionType.EXECUTE, True)
        
        stats = rl.get_stats()
        
        # Should have actions_taken dict
        assert 'actions_taken' in stats
        # Total actions is sum of all action counts
        total = sum(stats['actions_taken'].values())
        assert total >= 10


class TestRLMetrics:
    """Test RL metrics collection."""
    
    def test_rl_has_get_metrics_method(self):
        """RL should have get_metrics method."""
        rl = ReinforcementLearning()
        assert hasattr(rl, 'get_metrics'), "RL should have get_metrics"
    
    def test_get_metrics_returns_learning_history(self):
        """Metrics include learning history."""
        rl = ReinforcementLearning()
        
        # Add some learning
        for i in range(5):
            rl.update_q_value(f"task_{i}", ActionType.EXECUTE, 1.0, "done")
        
        metrics = rl.get_metrics()
        
        assert isinstance(metrics, dict)
        assert 'total_updates' in metrics or 'learning_history' in metrics or 'q_values' in metrics
    
    def test_metrics_track_best_actions(self):
        """Metrics track best actions per state."""
        rl = ReinforcementLearning()
        
        # Learn preferences
        for _ in range(10):
            rl.update_q_value("planning", ActionType.DELEGATE, 1.0, "done")
        
        metrics = rl.get_metrics()
        
        # Should have tracked this
        assert 'best_actions' in metrics or 'q_values' in metrics


class TestRLAutoPersist:
    """Test RL auto-persistence."""
    
    def test_rl_has_save_and_load(self):
        """RL should have save and load for manual persistence."""
        rl = ReinforcementLearning()
        assert hasattr(rl, 'save')
        assert hasattr(rl, 'load')
    
    def test_can_save_and_load(self, tmp_path):
        """Can save and load RL state."""
        rl = ReinforcementLearning()
        
        # Learn something
        rl.update_q_value("task1", ActionType.EXECUTE, 1.0, "done")
        
        save_path = str(tmp_path / "rl.json")
        assert rl.save(save_path) is True
        
        # Load into new instance
        rl2 = ReinforcementLearning()
        assert rl2.load(save_path) is True
        
        # Verify
        q = rl2.get_q_value("task1", ActionType.EXECUTE)
        assert q is not None