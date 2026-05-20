"""
Persistence Layer - Makes State Survive Restarts

TDD Tests verify:
- State save/load
- Crash recovery
- History persistence
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import time


@dataclass
class PersistedState:
    """State that survives restarts."""
    version: str = "1.0.0"
    last_save: float = 0.0
    task_history: list[dict[str, Any]] = None
    evolution_history: list[dict[str, Any]] = None
    security_violations: list[dict[str, Any]] = None
    learned_patterns: dict[str, Any] = None
    loop_metrics: dict[str, Any] = None
    pending_tasks: list[dict[str, Any]] = None
    previous_state: str = None
    goals: list[dict[str, Any]] = None
    
    def __post_init__(self):
        self.task_history = self.task_history or []
        self.evolution_history = self.evolution_history or []
        self.security_violations = self.security_violations or []
        self.learned_patterns = self.learned_patterns or {}
        self.loop_metrics = self.loop_metrics or {}
        self.pending_tasks = self.pending_tasks or []
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PersistedState:
        return cls(**data)


class PersistenceManager:
    """
    Handles persistence of loop state.
    
    Saves to disk so state survives restarts.
    """
    
    def __init__(self, storage_path: str | Path = "~/.hermes-pi-bridge/state.json"):
        self.storage_path = Path(os.path.expanduser(storage_path))
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = str(self.storage_path) + ".lock"
    
    def save(self, state: PersistedState) -> bool:
        """Save state to disk atomically."""
        try:
            state.last_save = time.time()
            data = state.to_dict()
            
            # Write to temp file first (atomic)
            temp_path = self.storage_path.with_suffix('.tmp')
            temp_path.write_text(json.dumps(data, indent=2))
            
            # Rename to actual path (atomic on POSIX)
            temp_path.rename(self.storage_path)
            
            return True
        except Exception as e:
            print(f"Save failed: {e}")
            return False
    
    def load(self) -> PersistedState | None:
        """Load state from disk."""
        try:
            if not self.storage_path.exists():
                return None
            
            data = json.loads(self.storage_path.read_text())
            return PersistedState.from_dict(data)
        except Exception as e:
            print(f"Load failed: {e}")
            return None
    
    def exists(self) -> bool:
        """Check if saved state exists."""
        return self.storage_path.exists()
    
    def delete(self) -> bool:
        """Delete saved state."""
        try:
            if self.storage_path.exists():
                self.storage_path.unlink()
            return True
        except Exception:
            return False
    
    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        if not self.exists():
            return {"exists": False, "size_bytes": 0}
        
        stat = self.storage_path.stat()
        return {
            "exists": True,
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
            "path": str(self.storage_path)
        }


class CrashRecovery:
    """Handles recovery from crashes."""
    
    def __init__(self, persistence: PersistenceManager):
        self.persistence = persistence
    
    def get_pending_tasks(self) -> list[dict[str, Any]]:
        """Get tasks that were in progress when crash occurred."""
        state = self.persistence.load()
        if not state:
            return []
        return state.pending_tasks or []
    
    def has_unfinished_work(self) -> bool:
        """Check if there are pending tasks after crash."""
        return len(self.get_pending_tasks()) > 0
    
    def mark_task_pending(self, task: dict[str, Any]) -> bool:
        """Mark a task as pending (in case of crash during execution)."""
        state = self.persistence.load() or PersistedState()
        if state.pending_tasks is None:
            state.pending_tasks = []
        
        # Add to pending if not already there
        task_ids = [t.get("task_id") for t in state.pending_tasks]
        if task.get("task_id") not in task_ids:
            task["pending_since"] = time.time()
            state.pending_tasks.append(task)
        
        return self.persistence.save(state)
    
    def mark_task_complete(self, task_id: str) -> bool:
        """Remove task from pending list."""
        state = self.persistence.load()
        if not state or not state.pending_tasks:
            return False
        
        state.pending_tasks = [
            t for t in state.pending_tasks 
            if t.get("task_id") != task_id
        ]
        
        return self.persistence.save(state)
    
    def get_recovery_report(self) -> dict[str, Any]:
        """Get report of what needs recovery."""
        pending = self.get_pending_tasks()
        return {
            "has_pending_tasks": len(pending) > 0,
            "pending_count": len(pending),
            "pending_tasks": pending,
            "recovery_needed": len(pending) > 0
        }
