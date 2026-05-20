"""
Learning Layer - Actually Learn from Experience

TDD Tests verify:
- Pattern recognition
- Success/failure rate tracking
- Capability improvement suggestions
- Adaptation based on history
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TaskPattern:
    """Recognized pattern from task history."""
    pattern_type: str  # "complexity", "capability", "success", "failure"
    pattern_key: str   # The actual pattern (e.g., "refactor", "testing")
    occurrences: int = 0
    success_rate: float = 0.0
    avg_duration: float = 0.0
    last_seen: float = 0.0
    
    def update(self, success: bool, duration: float) -> None:
        """Update pattern with new data point."""
        self.occurrences += 1
        self.last_seen = __import__('time').time()
        
        # Running average for success rate
        if self.occurrences == 1:
            self.success_rate = 1.0 if success else 0.0
            self.avg_duration = duration
        else:
            # New success rate = weighted average
            self.success_rate = (self.success_rate * (self.occurrences - 1) + (1.0 if success else 0.0)) / self.occurrences
            # New duration = weighted average
            self.avg_duration = (self.avg_duration * (self.occurrences - 1) + duration) / self.occurrences


@dataclass 
class CapabilityAssessment:
    """Assessment of agent capability in an area."""
    capability: str
    confidence: float  # 0.0 - 1.0
    success_rate: float
    avg_duration: float
    recommendation: str = ""


class PatternLearner:
    """
    Learns from task history to improve future decisions.
    
    This is the "brain" that actually makes the system self-improving.
    """
    
    # Keywords that indicate task types
    CAPABILITY_KEYWORDS = {
        "code_generation": ["create", "implement", "write", "add", "new function", "new class"],
        "code_review": ["review", "check", "audit", "validate"],
        "debugging": ["fix", "debug", "error", "exception", "traceback", "bug"],
        "refactoring": ["refactor", "restructure", "clean", "improve"],
        "testing": ["test", "spec", "verify", "assert", "coverage"],
        "documentation": ["doc", "readme", "comment", "document"],
        "research": ["research", "investigate", "analyze", "search", "find"],
        "file_operations": ["file", "read", "write", "read file", "write file"],
    }
    
    def __init__(self):
        self.patterns: dict[str, TaskPattern] = {}
        self.task_history: list[dict[str, Any]] = []
        self.max_history = 1000
    
    def learn_from_task(
        self,
        task_description: str,
        decision: str,
        success: bool,
        duration_seconds: float = 0.0,
        capabilities: list[str] = None
    ) -> None:
        """Learn from a completed task."""
        self.task_history.append({
            "description": task_description,
            "decision": decision,
            "success": success,
            "duration": duration_seconds,
            "capabilities": capabilities or [],
        })
        
        # Keep history bounded
        if len(self.task_history) > self.max_history:
            self.task_history = self.task_history[-self.max_history:]
        
        # Extract and update patterns
        desc_lower = task_description.lower()
        
        # Learn from capabilities
        for cap in capabilities or []:
            pattern_key = f"cap:{cap}"
            self._update_pattern(pattern_key, success, duration_seconds)
        
        # Learn from keywords
        for cap, keywords in self.CAPABILITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in desc_lower:
                    pattern_key = f"cap:{cap}"
                    self._update_pattern(pattern_key, success, duration_seconds)
        
        # Learn from complexity indicators
        if any(w in desc_lower for w in ["simple", "quick", "tiny"]):
            self._update_pattern("complexity:simple", success, duration_seconds)
        elif any(w in desc_lower for w in ["complex", "architect", "design"]):
            self._update_pattern("complexity:complex", success, duration_seconds)
        elif any(w in desc_lower for w in ["epic", "redesign", "rebuild"]):
            self._update_pattern("complexity:epic", success, duration_seconds)
    
    def _update_pattern(self, key: str, success: bool, duration: float) -> None:
        """Update a pattern with new data."""
        if key not in self.patterns:
            self.patterns[key] = TaskPattern(
                pattern_type=key.split(":")[0] if ":" in key else "unknown",
                pattern_key=key
            )
        self.patterns[key].update(success, duration)
    
    def get_capability_assessment(self, capability: str) -> CapabilityAssessment:
        """Get assessment of a specific capability."""
        pattern_key = f"cap:{capability}"
        pattern = self.patterns.get(pattern_key)
        
        if not pattern:
            return CapabilityAssessment(
                capability=capability,
                confidence=0.0,
                success_rate=0.0,
                avg_duration=0.0,
                recommendation="No history for this capability"
            )
        
        return CapabilityAssessment(
            capability=capability,
            confidence=min(pattern.occurrences / 10.0, 1.0),  # Max confidence at 10 samples
            success_rate=pattern.success_rate,
            avg_duration=pattern.avg_duration,
            recommendation=self._get_recommendation(pattern)
        )
    
    def _get_recommendation(self, pattern: TaskPattern) -> str:
        """Get recommendation based on pattern data."""
        if pattern.occurrences < 3:
            return "Need more samples to form recommendation"
        
        if pattern.success_rate < 0.5:
            return f"Low success rate ({pattern.success_rate:.0%}). Consider improving before delegation."
        
        if pattern.success_rate > 0.9:
            return f"High success rate ({pattern.success_rate:.0%}). Safe to delegate."
        
        return f"Moderate success rate ({pattern.success_rate:.0%}). Monitor closely."
    
    def suggest_improvements(self) -> list[str]:
        """Suggest improvements based on learned patterns."""
        suggestions = []
        
        # Find low-performing capabilities
        for key, pattern in self.patterns.items():
            if pattern.occurrences >= 3 and pattern.success_rate < 0.6:
                suggestions.append(
                    f"Improve {pattern.pattern_key}: only {pattern.success_rate:.0%} success rate"
                )
        
        # Find slow capabilities
        for key, pattern in self.patterns.items():
            if pattern.occurrences >= 3 and pattern.avg_duration > 300:  # > 5 min
                suggestions.append(
                    f"Optimize {pattern.pattern_key}: avg {pattern.avg_duration/60:.1f} min per task"
                )
        
        return suggestions
    
    def get_learned_stats(self) -> dict[str, Any]:
        """Get learning statistics."""
        total_patterns = len(self.patterns)
        high_confidence = sum(1 for p in self.patterns.values() if p.occurrences >= 5)
        
        return {
            "total_patterns": total_patterns,
            "high_confidence_patterns": high_confidence,
            "task_history_size": len(self.task_history),
            "patterns": {
                key: {
                    "occurrences": p.occurrences,
                    "success_rate": p.success_rate,
                    "avg_duration": p.avg_duration,
                }
                for key, p in self.patterns.items()
                if p.occurrences >= 3
            }
        }
    
    def should_delegate(
        self,
        description: str,
        capabilities: list[str]
    ) -> tuple[bool, float, str]:
        """
        Decide if task should be delegated based on learned patterns.
        
        Returns:
            Tuple of (should_delegate, confidence, reasoning)
        """
        desc_lower = description.lower()
        
        # Check each capability
        for cap in capabilities:
            assessment = self.get_capability_assessment(cap)
            
            if assessment.confidence > 0.5:
                if assessment.success_rate < 0.5:
                    return (
                        False,
                        assessment.confidence,
                        f"Low historical success rate ({assessment.success_rate:.0%}) for {cap}"
                    )
        
        # Check for unknown patterns (lower confidence)
        unknown_capabilities = []
        for cap, keywords in self.CAPABILITY_KEYWORDS.items():
            if any(kw in desc_lower for kw in keywords):
                if cap not in capabilities:
                    unknown_capabilities.append(cap)
        
        if unknown_capabilities:
            return (
                True,  # Still delegate, but...
                0.5,   # Lower confidence
                f"Partial match: {', '.join(unknown_capabilities)}"
            )
        
        return (
            True,
            0.8,
            "No negative patterns detected"
        )
