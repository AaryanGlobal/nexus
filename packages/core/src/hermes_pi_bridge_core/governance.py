"""
Bridge Governance Layer - Check/Balance Mechanism
Provides validation, rollback, TDD workflow, and confidence scoring
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
import time
import json


class DecisionConfidence(Enum):
    """Confidence levels for decisions."""
    LOW = "low"          # < 50% confidence - needs review
    MEDIUM = "medium"    # 50-80% confidence - proceed with caution
    HIGH = "high"        # > 80% confidence - proceed
    CERTAIN = "certain"  # 100% confidence - verified


class DecisionType(Enum):
    """Types of decisions the bridge can make."""
    EXECUTE_TASK = "execute_task"
    DELEGATE_TASK = "delegate_task"
    ROLLBACK = "rollback"
    SPLIT_TASK = "split_task"
    ESCALATE = "escalate"
    APPROVE_WORK = "approve_work"
    REJECT_WORK = "reject_work"


@dataclass
class Decision:
    """A decision made by the bridge."""
    id: str
    decision_type: DecisionType
    description: str
    confidence: DecisionConfidence
    reasoning: str
    timestamp: float
    approved: bool = False
    executed: bool = False
    result: Any = None


@dataclass
class RollbackPoint:
    """A point where we can rollback to."""
    id: str
    timestamp: float
    description: str
    state_snapshot: dict
    inverse_operation: Callable


class GovernanceConfig:
    """Configuration for governance layer."""
    def __init__(
        self,
        min_confidence_for_auto_approve: float = 0.8,
        max_consecutive_failures: int = 3,
        circuit_breaker_threshold: int = 5,
        rollback_enabled: bool = True,
        tdd_mode: bool = True
    ):
        self.min_confidence_for_auto_approve = min_confidence_for_auto_approve
        self.max_consecutive_failures = max_consecutive_failures
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.rollback_enabled = rollback_enabled
        self.tdd_mode = tdd_mode


class BridgeGovernance:
    """
    Governance layer for the bridge.
    
    Provides:
    - Decision validation before execution
    - Rollback capability
    - TDD workflow integration
    - Confidence scoring
    - Circuit breaker for failing loops
    - Decision audit trail
    """
    
    def __init__(self, config: GovernanceConfig | None = None):
        self.config = config or GovernanceConfig()
        self.decisions: list[Decision] = []
        self.rollback_stack: list[RollbackPoint] = []
        self.consecutive_failures: int = 0
        self.circuit_open: bool = False
        self.circuit_failures: int = 0
        
        # TDD state
        self.tdd_enabled = self.config.tdd_mode
        self.test_results: list[dict] = []
        
        # Confidence tracking
        self.decision_history: dict[str, list[bool]] = {}
    
    def validate_decision(self, decision_type: DecisionType, description: str, 
                         context: dict) -> tuple[Decision, bool]:
        """
        Validate a decision before execution.
        Returns (decision, should_proceed).
        """
        # Check circuit breaker
        if self.circuit_open:
            decision = self._create_decision(
                decision_type, description, DecisionConfidence.LOW,
                "Circuit breaker open - too many failures"
            )
            return decision, False
        
        # Calculate confidence based on history
        history = self.decision_history.get(decision_type.value, [])
        
        # Start with MEDIUM confidence for no history
        if not history:
            confidence = DecisionConfidence.MEDIUM
            should_proceed = True
        else:
            # Calculate based on history
            success_rate = sum(history) / len(history)
            samples = len(history)
            
            if samples >= 10 and success_rate >= 0.9:
                confidence = DecisionConfidence.CERTAIN
                should_proceed = True
            elif samples >= 5 and success_rate >= 0.8:
                confidence = DecisionConfidence.HIGH
                should_proceed = True
            elif success_rate >= 0.5:
                confidence = DecisionConfidence.MEDIUM
                should_proceed = True
            else:
                confidence = DecisionConfidence.LOW
                should_proceed = False
        
        decision = self._create_decision(
            decision_type, description, confidence,
            self._get_reasoning(decision_type, context, confidence)
        )
        
        self.decisions.append(decision)
        return decision, should_proceed
    
    def approve_decision(self, decision_id: str, approver: str = "user") -> bool:
        """Approve a decision manually."""
        for d in self.decisions:
            if d.id == decision_id:
                d.approved = True
                return True
        return False
    
    def execute_decision(self, decision_id: str, executor: Callable) -> Any:
        """Execute an approved decision."""
        for d in self.decisions:
            if d.id == decision_id:
                if d.confidence == DecisionConfidence.LOW and not d.approved:
                    raise ValueError("Cannot execute low-confidence unapproved decision")
                
                try:
                    d.result = executor()
                    d.executed = True
                    self._record_outcome(d, True)
                    self.consecutive_failures = 0
                    return d.result
                except Exception as e:
                    d.result = str(e)
                    self._record_outcome(d, False)
                    self.consecutive_failures += 1
                    self._check_circuit_breaker()
                    raise
        
        raise ValueError(f"Decision {decision_id} not found")
    
    def create_rollback_point(self, description: str, state: dict, 
                             inverse_op: Callable) -> str:
        """Create a rollback point."""
        point = RollbackPoint(
            id=f"rb-{time.time()}",
            timestamp=time.time(),
            description=description,
            state_snapshot=state,
            inverse_operation=inverse_op
        )
        self.rollback_stack.append(point)
        return point.id
    
    def rollback(self, steps: int = 1) -> list[Any]:
        """Rollback to a previous state."""
        if not self.config.rollback_enabled:
            return []
        
        results = []
        for _ in range(min(steps, len(self.rollback_stack))):
            point = self.rollback_stack.pop()
            try:
                result = point.inverse_operation()
                results.append(result)
                self._record_outcome(self._create_decision(
                    DecisionType.ROLLBACK, point.description,
                    DecisionConfidence.HIGH, f"Rolled back: {point.description}"
                ), True)
            except Exception as e:
                results.append(f"Rollback failed: {e}")
        
        return results
    
    def run_tdd_cycle(self, test_func: Callable, code_func: Callable,
                     max_retries: int = 3) -> dict:
        """
        Run a TDD cycle: RED -> GREEN -> REFACTOR.
        
        Returns:
            dict with 'phase', 'passed', 'attempts', 'result'
        """
        if not self.tdd_enabled:
            return {'phase': 'disabled', 'passed': False}
        
        # RED phase - Write failing test
        test_result = {'phase': 'red', 'passed': False, 'attempts': 0}
        try:
            test_func()
            test_result['attempts'] = 1
        except AssertionError:
            test_result['attempts'] = 1
            test_result['passed'] = True  # Expected failure
        except Exception as e:
            test_result['error'] = str(e)
            return test_result
        
        # GREEN phase - Make it pass
        for attempt in range(max_retries):
            test_result['attempts'] = attempt + 1
            try:
                code_func()
                # Refactor phase - Run test again
                test_func()
                test_result['phase'] = 'green'
                test_result['passed'] = True
                break
            except:
                if attempt == max_retries - 1:
                    test_result['phase'] = 'failed'
        
        self.test_results.append(test_result)
        return test_result
    
    def _calculate_confidence(self, decision_type: DecisionType, 
                            context: dict) -> DecisionConfidence:
        """Calculate confidence in a decision based on history."""
        # Get historical success rate for this decision type
        history = self.decision_history.get(decision_type.value, [])
        
        if not history:
            return DecisionConfidence.MEDIUM
        
        success_rate = sum(history) / len(history)
        
        # Adjust based on history length
        samples = len(history)
        if samples >= 10:
            if success_rate >= 0.9:
                return DecisionConfidence.CERTAIN
            elif success_rate >= 0.8:
                return DecisionConfidence.HIGH
            elif success_rate >= 0.5:
                return DecisionConfidence.MEDIUM
            else:
                return DecisionConfidence.LOW
        else:
            # Fewer samples = lower confidence
            if success_rate >= 0.9:
                return DecisionConfidence.HIGH
            elif success_rate >= 0.7:
                return DecisionConfidence.MEDIUM
            else:
                return DecisionConfidence.LOW
    
    def _get_reasoning(self, decision_type: DecisionType, context: dict,
                      confidence: DecisionConfidence) -> str:
        """Generate reasoning for a decision."""
        if confidence == DecisionConfidence.LOW:
            return f"Low confidence - need more data for {decision_type.value}"
        elif confidence == DecisionConfidence.MEDIUM:
            return f"Proceed with caution - {decision_type.value}"
        elif confidence == DecisionConfidence.HIGH:
            return f"High confidence based on history"
        else:
            return f"Certain - validated multiple times"
    
    def _record_outcome(self, decision: Decision, success: bool):
        """Record the outcome of a decision."""
        history = self.decision_history.setdefault(decision.decision_type.value, [])
        history.append(success)
        
        # Keep history bounded
        if len(history) > 100:
            history.pop(0)
    
    def _check_circuit_breaker(self):
        """Check and update circuit breaker state."""
        self.circuit_failures = self.consecutive_failures
        
        if self.circuit_failures >= self.config.circuit_breaker_threshold:
            self.circuit_open = True
    
    def reset_circuit(self):
        """Reset the circuit breaker."""
        self.circuit_open = False
        self.circuit_failures = 0
        self.consecutive_failures = 0
    
    def _create_decision(self, decision_type: DecisionType, description: str,
                        confidence: DecisionConfidence, reasoning: str) -> Decision:
        """Create a new decision."""
        return Decision(
            id=f"dec-{time.time()}-{len(self.decisions)}",
            decision_type=decision_type,
            description=description,
            confidence=confidence,
            reasoning=reasoning,
            timestamp=time.time()
        )
    
    def get_confidence_score(self, decision_type: DecisionType) -> float:
        """Get numerical confidence score (0-1)."""
        mapping = {
            DecisionConfidence.LOW: 0.3,
            DecisionConfidence.MEDIUM: 0.65,
            DecisionConfidence.HIGH: 0.85,
            DecisionConfidence.CERTAIN: 1.0
        }
        
        context = {'decision_type': decision_type}
        confidence = self._calculate_confidence(decision_type, context)
        return mapping.get(confidence, 0.5)
    
    def get_governance_report(self) -> dict:
        """Get a report of governance status."""
        return {
            'circuit_open': self.circuit_open,
            'consecutive_failures': self.consecutive_failures,
            'total_decisions': len(self.decisions),
            'decisions_by_confidence': self._count_by_confidence(),
            'tdd_enabled': self.tdd_enabled,
            'tdd_results': len(self.test_results),
            'rollback_points': len(self.rollback_stack),
            'confidence_scores': {
                dt.value: self.get_confidence_score(dt)
                for dt in DecisionType
            }
        }
    
    def _count_by_confidence(self) -> dict:
        """Count decisions by confidence level."""
        counts = {c.value: 0 for c in DecisionConfidence}
        for d in self.decisions:
            counts[d.confidence.value] += 1
        return counts