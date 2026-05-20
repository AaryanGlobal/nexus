"""TDD: Persistence Layer Tests"""
import pytest
import os
import tempfile
from pathlib import Path
from hermes_pi_bridge_core.persistence import (
    PersistenceManager, PersistedState, CrashRecovery
)


class TestPersistedState:
    """Test persisted state structure."""
    
    def test_default_state(self):
        state = PersistedState()
        assert state.version == "1.0.0"
        assert state.task_history == []
        assert state.evolution_history == []
        assert state.pending_tasks == []
    
    def test_to_dict(self):
        state = PersistedState()
        state.task_history = [{"task_id": "test-1"}]
        data = state.to_dict()
        assert data["task_history"][0]["task_id"] == "test-1"
    
    def test_from_dict(self):
        data = {
            "version": "1.0.0",
            "last_save": 123456.0,
            "task_history": [{"task_id": "test-1"}],
            "evolution_history": [],
            "security_violations": [],
            "learned_patterns": {},
            "loop_metrics": {},
            "pending_tasks": []
        }
        state = PersistedState.from_dict(data)
        assert state.task_history[0]["task_id"] == "test-1"


class TestPersistenceManager:
    """Test persistence manager."""
    
    def test_default_path_expansion(self):
        pm = PersistenceManager()
        assert "~" not in str(pm.storage_path)
        assert ".hermes-pi-bridge" in str(pm.storage_path)
    
    def test_custom_path(self, tmp_path):
        pm = PersistenceManager(tmp_path / "test_state.json")
        assert pm.storage_path == tmp_path / "test_state.json"
    
    def test_save_and_load(self, tmp_path):
        pm = PersistenceManager(tmp_path / "state.json")
        
        state = PersistedState()
        state.task_history = [{"task_id": "test-1", "status": "done"}]
        
        assert pm.save(state) is True
        assert pm.exists() is True
        
        loaded = pm.load()
        assert loaded is not None
        assert loaded.task_history[0]["task_id"] == "test-1"
    
    def test_load_nonexistent(self, tmp_path):
        pm = PersistenceManager(tmp_path / "nonexistent.json")
        assert pm.load() is None
    
    def test_delete(self, tmp_path):
        pm = PersistenceManager(tmp_path / "state.json")
        
        state = PersistedState()
        pm.save(state)
        assert pm.exists() is True
        
        pm.delete()
        assert pm.exists() is False
    
    def test_get_stats_nonexistent(self, tmp_path):
        pm = PersistenceManager(tmp_path / "nonexistent.json")
        stats = pm.get_stats()
        assert stats["exists"] is False
    
    def test_get_stats_existing(self, tmp_path):
        pm = PersistenceManager(tmp_path / "state.json")
        pm.save(PersistedState())
        
        stats = pm.get_stats()
        assert stats["exists"] is True
        assert stats["size_bytes"] > 0
    
    def test_overwrite_existing(self, tmp_path):
        pm = PersistenceManager(tmp_path / "state.json")
        
        # Save first version
        state1 = PersistedState()
        state1.task_history = [{"task_id": "v1"}]
        pm.save(state1)
        
        # Save second version
        state2 = PersistedState()
        state2.task_history = [{"task_id": "v2"}]
        pm.save(state2)
        
        loaded = pm.load()
        assert loaded.task_history[0]["task_id"] == "v2"


class TestCrashRecovery:
    """Test crash recovery functionality."""
    
    def test_no_pending_on_fresh_start(self, tmp_path):
        pm = PersistenceManager(tmp_path / "state.json")
        cr = CrashRecovery(pm)
        assert cr.get_pending_tasks() == []
        assert cr.has_unfinished_work() is False
    
    def test_mark_task_pending(self, tmp_path):
        pm = PersistenceManager(tmp_path / "state.json")
        cr = CrashRecovery(pm)
        
        task = {"task_id": "crash-task-1", "description": "Important task"}
        cr.mark_task_pending(task)
        
        pending = cr.get_pending_tasks()
        assert len(pending) == 1
        assert pending[0]["task_id"] == "crash-task-1"
    
    def test_mark_task_complete(self, tmp_path):
        pm = PersistenceManager(tmp_path / "state.json")
        cr = CrashRecovery(pm)
        
        task = {"task_id": "crash-task-1"}
        cr.mark_task_pending(task)
        assert cr.has_unfinished_work() is True
        
        cr.mark_task_complete("crash-task-1")
        assert cr.has_unfinished_work() is False
    
    def test_no_duplicate_pending(self, tmp_path):
        pm = PersistenceManager(tmp_path / "state.json")
        cr = CrashRecovery(pm)
        
        cr.mark_task_pending({"task_id": "same-task"})
        cr.mark_task_pending({"task_id": "same-task"})
        
        pending = cr.get_pending_tasks()
        assert len(pending) == 1  # Only one entry
    
    def test_recovery_report_no_pending(self, tmp_path):
        pm = PersistenceManager(tmp_path / "state.json")
        cr = CrashRecovery(pm)
        
        report = cr.get_recovery_report()
        assert report["recovery_needed"] is False
        assert report["pending_count"] == 0
    
    def test_recovery_report_with_pending(self, tmp_path):
        pm = PersistenceManager(tmp_path / "state.json")
        cr = CrashRecovery(pm)
        
        cr.mark_task_pending({"task_id": "pending-1"})
        cr.mark_task_pending({"task_id": "pending-2"})
        
        report = cr.get_recovery_report()
        assert report["recovery_needed"] is True
        assert report["pending_count"] == 2


class TestPersistenceIntegration:
    """Integration tests for persistence."""
    
    def test_save_large_history(self, tmp_path):
        """Test handling of large task history."""
        pm = PersistenceManager(tmp_path / "state.json")
        
        state = PersistedState()
        state.task_history = [
            {"task_id": f"task-{i}", "status": "done"}
            for i in range(100)
        ]
        
        pm.save(state)
        loaded = pm.load()
        
        assert len(loaded.task_history) == 100
    
    def test_preserves_nested_data(self, tmp_path):
        """Test nested data structures preserved."""
        pm = PersistenceManager(tmp_path / "state.json")
        
        state = PersistedState()
        state.loop_metrics = {
            "tasks_completed": 42,
            "nested": {"deep": {"value": 123}}
        }
        state.learned_patterns = {
            "common_tasks": [
                {"type": "testing", "count": 10}
            ]
        }
        
        pm.save(state)
        loaded = pm.load()
        
        assert loaded.loop_metrics["tasks_completed"] == 42
        assert loaded.loop_metrics["nested"]["deep"]["value"] == 123
        assert loaded.learned_patterns["common_tasks"][0]["type"] == "testing"
