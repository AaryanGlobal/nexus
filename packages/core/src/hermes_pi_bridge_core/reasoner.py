"""
Task Reasoner - Decides WHAT to delegate

Uses AI to analyze:
- Task complexity vs. capability match
- Delegation cost/benefit analysis
- Dependency analysis
- Optimal agent selection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DelegationDecision(StrEnum):
    """Decisions from the reasoner."""
    DELEGATE_TO_PI = "delegate_to_pi"      # Send to pi for execution
    DELEGATE_TO_HERMES = "delegate_to_hermes"  # Send to Hermes (or external)
    HANDLE_SELF = "handle_self"             # Process internally
    SPLIT_AND_DELEGATE = "split_and_delegate"  # Break into subtasks
    REJECT = "reject"                       # Don't execute


class TaskComplexity(StrEnum):
    """Complexity assessment."""
    TRIVIAL = "trivial"      # <1 min, no planning needed
    SIMPLE = "simple"       # 1-5 min, straightforward
    MODERATE = "moderate"   # 5-30 min, some planning
    COMPLEX = "complex"     # 30-120 min, significant planning
    EPIC = "epic"           # >2 hours, multi-phase


class AgentCapability(StrEnum):
    """Agent capability areas."""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    RESEARCH = "research"
    FILE_OPERATIONS = "file_operations"
    COMMAND_EXECUTION = "command_execution"
    DATA_ANALYSIS = "data_analysis"


@dataclass
class DelegationReason:
    """Reason for delegation decision."""
    decision: DelegationDecision
    confidence: float  # 0.0 - 1.0
    reasoning: str
    suggested_priority: str = "normal"
    estimated_duration_minutes: int = 5
    subtasks: list[dict[str, Any]] = field(default_factory=list)
    capability_match: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class TaskAnalysis:
    """Analysis of a task for delegation."""
    task_id: str
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    complexity: TaskComplexity = TaskComplexity.SIMPLE
    required_capabilities: list[AgentCapability] = field(default_factory=list)
    estimated_duration_minutes: int = 5
    has_side_effects: bool = False
    is_idempotent: bool = True
    requires_human_approval: bool = False
    dependencies: list[str] = field(default_factory=list)


class TaskReasoner:
    """
    Analyzes tasks and decides delegation strategy.
    
    TDD Tests verify:
    - Complexity assessment
    - Capability matching
    - Cost-benefit analysis
    - Decision confidence
    """
    
    # Complexity indicators
    COMPLEXITY_KEYWORDS = {
        TaskComplexity.TRIVIAL: ["quick", "simple", "one line", "tiny"],
        TaskComplexity.SIMPLE: ["file", "read", "write", "check", "list"],
        TaskComplexity.MODERATE: ["implement", "create", "refactor", "update"],
        TaskComplexity.COMPLEX: ["architect", "design", "migrate", "optimize"],
        TaskComplexity.EPIC: ["redesign", "rebuild", "multi-phase", "enterprise"]
    }
    
    # pi strengths (tactical, execution-focused)
    PI_CAPABILITIES = {
        AgentCapability.CODE_GENERATION,
        AgentCapability.CODE_REVIEW,
        AgentCapability.DEBUGGING,
        AgentCapability.TESTING,
        AgentCapability.DOCUMENTATION,
        AgentCapability.FILE_OPERATIONS,
        AgentCapability.COMMAND_EXECUTION,
    }
    
    # Hermes strengths (strategic, planning-focused)
    HERMES_CAPABILITIES = {
        AgentCapability.RESEARCH,
        AgentCapability.DATA_ANALYSIS,
    }
    
    def __init__(
        self,
        pi_capabilities: set[AgentCapability] | None = None,
        hermes_capabilities: set[AgentCapability] | None = None,
        auto_delegate_threshold: float = 0.7,
    ):
        self.pi_capabilities = pi_capabilities or self.PI_CAPABILITIES
        self.hermes_capabilities = hermes_capabilities or self.HERMES_CAPABILITIES
        self.auto_delegate_threshold = auto_delegate_threshold
    
    def analyze_task(self, description: str, context: dict[str, Any] = None) -> TaskAnalysis:
        """Analyze a task to understand its nature."""
        context = context or {}
        desc_lower = description.lower()
        
        # Assess complexity
        complexity = self._assess_complexity(desc_lower)
        
        # Identify required capabilities
        capabilities = self._identify_capabilities(desc_lower)
        
        # Estimate duration
        duration = self._estimate_duration(desc_lower, complexity)
        
        # Check for side effects
        has_side_effects = any(kw in desc_lower for kw in [
            "delete", "remove", "drop", "update all", "replace",
            "sudo", "rm ", "chmod", "chown"
        ])
        
        # Check for idempotency
        is_idempotent = not has_side_effects and "create" not in desc_lower
        
        return TaskAnalysis(
            task_id=context.get("task_id", "unknown"),
            description=description,
            context=context,
            complexity=complexity,
            required_capabilities=capabilities,
            estimated_duration_minutes=duration,
            has_side_effects=has_side_effects,
            is_idempotent=is_idempotent,
            requires_human_approval=has_side_effects and "force" not in desc_lower,
        )
    
    def _assess_complexity(self, description: str) -> TaskComplexity:
        """Assess task complexity from description."""
        for complexity, keywords in sorted(
            self.COMPLEXITY_KEYWORDS.items(),
            key=lambda x: list(x[1])[0],  # Sort by first keyword
            reverse=True  # Epic first
        ):
            if any(kw in description for kw in keywords):
                return complexity
        return TaskComplexity.SIMPLE
    
    def _identify_capabilities(self, description: str) -> list[AgentCapability]:
        """Identify required capabilities from description."""
        capabilities = []
        
        capability_map = {
            "def|function|class|method|interface": AgentCapability.CODE_GENERATION,
            "review|check|audit": AgentCapability.CODE_REVIEW,
            "debug|fix|error|exception|traceback": AgentCapability.DEBUGGING,
            "refactor|restructure|clean": AgentCapability.REFACTORING,
            "test|spec|verify|assert": AgentCapability.TESTING,
            "doc|readme|comment": AgentCapability.DOCUMENTATION,
            "research|investigate|analyze|search": AgentCapability.RESEARCH,
            "file|read|write|open|create": AgentCapability.FILE_OPERATIONS,
            "run|execute|bash|shell|command": AgentCapability.COMMAND_EXECUTION,
        }
        
        for pattern, cap in capability_map.items():
            import re
            if re.search(pattern, description):
                capabilities.append(cap)
        
        return capabilities or [AgentCapability.CODE_GENERATION]
    
    def _estimate_duration(self, description: str, complexity: TaskComplexity) -> int:
        """Estimate task duration in minutes."""
        base_durations = {
            TaskComplexity.TRIVIAL: 1,
            TaskComplexity.SIMPLE: 5,
            TaskComplexity.MODERATE: 15,
            TaskComplexity.COMPLEX: 60,
            TaskComplexity.EPIC: 120,
        }
        
        base = base_durations[complexity]
        
        # Adjust for scope indicators
        if "multiple" in description or "several" in description:
            base *= 2
        if "single" in description or "one" in description:
            base = int(base * 0.5)
        
        return min(base, 480)  # Cap at 8 hours
    
    def decide(self, analysis: TaskAnalysis) -> DelegationReason:
        """
        Decide delegation strategy based on analysis.
        
        Decision logic:
        1. If pi has all required capabilities → delegate to pi
        2. If hermes has required capabilities → delegate to hermes
        3. If task is trivial → handle self
        4. If task is epic → split and delegate
        """
        reasoning_parts = []
        warnings = []
        
        # Check capability match
        pi_match = self._calculate_capability_match(
            analysis.required_capabilities,
            self.pi_capabilities
        )
        hermes_match = self._calculate_capability_match(
            analysis.required_capabilities,
            self.hermes_capabilities
        )
        
        capability_match = {
            "pi": pi_match,
            "hermes": hermes_match
        }
        
        # Decision logic
        if analysis.requires_human_approval:
            decision = DelegationDecision.REJECT
            reasoning_parts.append("Task requires human approval")
            warnings.append("Task has potential side effects")
        
        elif analysis.complexity == TaskComplexity.EPIC:
            decision = DelegationDecision.SPLIT_AND_DELEGATE
            reasoning_parts.append("Epic task split into phases")
            # Generate subtasks
            subtasks = self._split_epic_task(analysis)
        
        elif analysis.complexity == TaskComplexity.TRIVIAL:
            decision = DelegationDecision.HANDLE_SELF
            reasoning_parts.append("Task is trivial, no delegation needed")
        
        elif pi_match >= hermes_match and pi_match >= self.auto_delegate_threshold:
            decision = DelegationDecision.DELEGATE_TO_PI
            reasoning_parts.append(f"pi has {pi_match:.0%} capability match")
        
        elif hermes_match > pi_match:
            decision = DelegationDecision.DELEGATE_TO_HERMES
            reasoning_parts.append(f"hermes has {hermes_match:.0%} capability match")
        
        else:
            # Default to pi for balanced workload
            decision = DelegationDecision.DELEGATE_TO_PI
            reasoning_parts.append("Default delegation to pi for balanced workload")
        
        # Calculate confidence
        confidence = max(pi_match, hermes_match) if decision != DelegationDecision.HANDLE_SELF else 0.8
        
        return DelegationReason(
            decision=decision,
            confidence=confidence,
            reasoning=" ".join(reasoning_parts),
            suggested_priority=self._determine_priority(analysis),
            estimated_duration_minutes=analysis.estimated_duration_minutes,
            subtasks=subtasks if analysis.complexity == TaskComplexity.EPIC else [],
            capability_match=capability_match,
            warnings=warnings,
        )
    
    def _calculate_capability_match(
        self,
        required: list[AgentCapability],
        available: set[AgentCapability]
    ) -> float:
        """Calculate how well capabilities match."""
        if not required:
            return 1.0
        matched = sum(1 for cap in required if cap in available)
        return matched / len(required)
    
    def _split_epic_task(self, analysis: TaskAnalysis) -> list[dict[str, Any]]:
        """Split epic task into manageable subtasks."""
        return [
            {
                "task_id": f"{analysis.task_id}-phase-1",
                "title": f"Phase 1: Research and Planning - {analysis.description[:50]}",
                "priority": "high"
            },
            {
                "task_id": f"{analysis.task_id}-phase-2", 
                "title": f"Phase 2: Implementation - {analysis.description[:50]}",
                "priority": "high"
            },
            {
                "task_id": f"{analysis.task_id}-phase-3",
                "title": f"Phase 3: Testing and Validation - {analysis.description[:50]}",
                "priority": "normal"
            }
        ]
    
    def _determine_priority(self, analysis: TaskAnalysis) -> str:
        """Determine task priority."""
        if analysis.has_side_effects:
            return "high"
        if analysis.complexity in (TaskComplexity.EPIC, TaskComplexity.COMPLEX):
            return "high"
        if analysis.estimated_duration_minutes > 60:
            return "high"
        return "normal"
