"""
Goal Management - Captures and tracks user needs/goals

TDD Tests verify:
- Goals can be created from ideation
- Goals progress toward completion
- Goals persist and survive restarts
- Suggestions are generated from goals
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from enum import StrEnum


class GoalStatus(StrEnum):
    """Goal status values."""
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class GoalPriority(StrEnum):
    """Goal priority levels."""
    CRITICAL = "critical"  # Must achieve
    HIGH = "high"          # Important
    MEDIUM = "medium"      # Normal
    LOW = "low"           # Nice to have


@dataclass
class Goal:
    """A goal that the system works toward."""
    id: str
    title: str
    description: str
    status: GoalStatus = GoalStatus.ACTIVE
    priority: GoalPriority = GoalPriority.MEDIUM
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    progress: float = 0.0  # 0.0 to 1.0
    tasks: list[dict] = field(default_factory=list)
    milestones: list[dict] = field(default_factory=list)
    learnings: list[str] = field(default_factory=list)
    iterations: int = 0
    metadata: dict = field(default_factory=dict)
    
    def is_achieved(self) -> bool:
        """Check if goal is achieved."""
        return self.status == GoalStatus.COMPLETED
    
    def add_task(self, task: dict) -> None:
        """Add a task toward this goal."""
        self.tasks.append(task)
        self.updated_at = time.time()
    
    def update_progress(self, progress: float) -> None:
        """Update goal progress."""
        self.progress = max(0.0, min(1.0, progress))
        self.updated_at = time.time()
        if self.progress >= 1.0:
            self.status = GoalStatus.COMPLETED
            self.completed_at = time.time()
    
    def add_learning(self, learning: str) -> None:
        """Add a learning from working on this goal."""
        self.learnings.append(learning)
        self.updated_at = time.time()


class GoalManager:
    """
    Manages user goals and works toward their achievement.
    
    This is the "common space" where user needs are captured
    and the system works toward their completion.
    """
    
    def __init__(self, storage_path: str | None = None):
        self.storage_path = storage_path or "~/.hermes-pi-bridge/goals.json"
        self.goals: list[Goal] = []
        self.current_goal: Goal | None = None
        self.suggestions: list[str] = []
        self._load_goals()
    
    def _load_goals(self) -> None:
        """Load goals from storage."""
        import json
        path = self.storage_path.replace("~", str(__import__('pathlib').Path.home()))
        try:
            with open(path) as f:
                data = json.load(f)
                self.goals = [Goal(**g) for g in data.get('goals', [])]
        except Exception:
            pass
    
    def _save_goals(self) -> bool:
        """Save goals to storage."""
        import json
        path = self.storage_path.replace("~", str(__import__('pathlib').Path.home()))
        try:
            with open(path, 'w') as f:
                json.dump({'goals': [g.__dict__ for g in self.goals]}, f)
            return True
        except Exception:
            return False
    
    def add_goal(self, title: str, description: str, priority: GoalPriority = GoalPriority.MEDIUM) -> Goal:
        """Add a new goal from ideation."""
        goal = Goal(
            id=f"goal-{time.time()}",
            title=title,
            description=description,
            priority=priority,
        )
        self.goals.append(goal)
        self._save_goals()
        return goal
    
    def add_ideation(self, content: str) -> list[Goal]:
        """
        Process ideation content and extract goals.
        
        Called when user puts things in the common space.
        Parses content to find goals/needs.
        """
        goals_created = []
        
        # Simple parsing - look for actionable items
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            
            # Check for priority markers (exact match)
            priority = GoalPriority.MEDIUM
            line_upper = line.upper()
            
            if line_upper.startswith('[CRITICAL]') or '[CRITICAL]' in line_upper:
                priority = GoalPriority.CRITICAL
                line = line.replace('[CRITICAL]', '').replace('[CRITICAL]', '')
            elif line_upper.startswith('[URGENT]') or '[URGENT]' in line_upper:
                priority = GoalPriority.CRITICAL
                line = line.replace('[URGENT]', '').replace('[URGENT]', '')
            elif line_upper.startswith('[HIGH]') or ' [HIGH]' in line_upper:
                priority = GoalPriority.HIGH
                line = line.replace('[HIGH]', '').replace('[HIGH]', '')
            elif line_upper.startswith('[LOW]') or ' [LOW]' in line_upper:
                priority = GoalPriority.LOW
                line = line.replace('[LOW]', '').replace('[LOW]', '')
            
            # Create goal if it looks actionable
            line = line.strip()
            if len(line) > 5:
                goal = self.add_goal(line, f"Ideation: {line}", priority)
                goals_created.append(goal)
        
        return goals_created
    
    def get_active_goals(self) -> list[Goal]:
        """Get all active goals."""
        return [g for g in self.goals if g.status in [GoalStatus.ACTIVE, GoalStatus.IN_PROGRESS]]
    
    def get_next_goal(self) -> Goal | None:
        """Get the next goal to work on (highest priority first)."""
        if not self.goals:
            return None
        
        # Sort by priority and age
        priority_order = {
            GoalPriority.CRITICAL: 0,
            GoalPriority.HIGH: 1,
            GoalPriority.MEDIUM: 2,
            GoalPriority.LOW: 3,
        }
        
        active = self.get_active_goals()
        if not active:
            return None
        
        active.sort(key=lambda g: (priority_order.get(g.priority, 3), g.created_at))
        return active[0]
    
    def work_on_goal(self, goal_id: str) -> Goal | None:
        """Mark a goal as being worked on."""
        for goal in self.goals:
            if goal.id == goal_id:
                goal.status = GoalStatus.IN_PROGRESS
                goal.iterations += 1
                goal.updated_at = time.time()
                self.current_goal = goal
                self._save_goals()
                return goal
        return None
    
    def update_goal_progress(self, goal_id: str, progress: float, task: str | None = None) -> Goal | None:
        """Update progress on a goal."""
        for goal in self.goals:
            if goal.id == goal_id:
                goal.update_progress(progress)
                if task:
                    goal.add_task({
                        'task': task,
                        'progress': progress,
                        'timestamp': time.time(),
                    })
                self._save_goals()
                return goal
        return None
    
    def complete_goal(self, goal_id: str, learnings: list[str] | None = None) -> Goal | None:
        """Mark a goal as completed."""
        for goal in self.goals:
            if goal.id == goal_id:
                goal.status = GoalStatus.COMPLETED
                goal.progress = 1.0
                goal.completed_at = time.time()
                if learnings:
                    goal.learnings.extend(learnings)
                self._save_goals()
                return goal
        return None
    
    def generate_suggestions(self) -> list[str]:
        """Generate suggestions based on goals and learnings."""
        suggestions = []
        
        # Suggest next steps based on current goal
        current = self.get_next_goal()
        if current:
            suggestions.append(f"Work on: {current.title}")
            if current.description:
                suggestions.append(f"Context: {current.description[:100]}")
            suggestions.append(f"Progress: {current.progress * 100:.0f}%")
        
        # Suggest based on learnings
        if self.goals:
            completed = [g for g in self.goals if g.is_achieved()]
            if completed:
                suggestions.append(f"Achieved {len(completed)} goals!")
            
            # Suggest blocked goals might need attention
            blocked = [g for g in self.goals if g.status == GoalStatus.BLOCKED]
            if blocked:
                suggestions.append(f"Review {len(blocked)} blocked goals")
        
        self.suggestions = suggestions
        return suggestions
    
    def get_status_summary(self) -> dict[str, Any]:
        """Get summary of all goals."""
        total = len(self.goals)
        completed = sum(1 for g in self.goals if g.is_achieved())
        active = sum(1 for g in self.goals if g.status == GoalStatus.IN_PROGRESS)
        blocked = sum(1 for g in self.goals if g.status == GoalStatus.BLOCKED)
        
        return {
            'total_goals': total,
            'completed': completed,
            'in_progress': active,
            'blocked': blocked,
            'completion_rate': completed / total if total > 0 else 0,
            'current_goal': self.current_goal.title if self.current_goal else None,
            'suggestions': self.generate_suggestions(),
        }
