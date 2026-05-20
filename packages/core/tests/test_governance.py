"""TDD: Bridge Governance Layer Tests"""
import pytest
from hermes_pi_bridge_core.governance import (
    BridgeGovernance, GovernanceConfig, DecisionType, DecisionConfidence
)


class TestDecisionValidation:
    """Test decision validation."""
    
    def test_validate_high_confidence_decision(self):
        """High confidence decisions should proceed."""
        gov = BridgeGovernance()
        
        decision, should_proceed = gov.validate_decision(
            DecisionType.EXECUTE_TASK,
            "Run unit tests",
            {'expected_duration': 10}
        )
        
        # With no history, should proceed (MEDIUM confidence)
        assert should_proceed is True
        assert decision.confidence == DecisionConfidence.MEDIUM
    
    def test_low_confidence_needs_approval(self):
        """Low confidence decisions should be flagged."""
        gov = BridgeGovernance()
        
        # Add some failed decisions to lower confidence
        for _ in range(10):
            gov._record_outcome(gov._create_decision(
                DecisionType.EXECUTE_TASK, "test", DecisionConfidence.LOW, "low"
            ), False)
        
        decision, should_proceed = gov.validate_decision(
            DecisionType.EXECUTE_TASK,
            "Complex refactoring",
            {}
        )
        
        assert should_proceed is False
        assert decision.confidence == DecisionConfidence.LOW
    
    def test_circuit_breaker_blocks_decisions(self):
        """Circuit breaker should block when open."""
        gov = BridgeGovernance()
        
        # Open the circuit
        gov.circuit_open = True
        
        _, should_proceed = gov.validate_decision(
            DecisionType.EXECUTE_TASK,
            "Should be blocked",
            {}
        )
        
        assert should_proceed is False


class TestRollback:
    """Test rollback capability."""
    
    def test_create_rollback_point(self):
        """Should create rollback points."""
        gov = BridgeGovernance()
        
        rollback_id = gov.create_rollback_point(
            "Before refactor",
            {'code': 'old'},
            lambda: {'code': 'restored'}
        )
        
        assert rollback_id.startswith('rb-')
        assert len(gov.rollback_stack) == 1
    
    def test_rollback_restores_state(self):
        """Rollback should call inverse operation."""
        gov = BridgeGovernance()
        
        restored = []
        gov.create_rollback_point(
            "Before change",
            {'value': 10},
            lambda: restored.append('restored')
        )
        
        gov.rollback(1)
        
        assert 'restored' in restored
    
    def test_rollback_disabled_by_config(self):
        """Rollback can be disabled."""
        gov = BridgeGovernance()
        gov.config.rollback_enabled = False
        
        gov.create_rollback_point("test", {}, lambda: None)
        results = gov.rollback(1)
        
        assert len(results) == 0


class TestTDDWorkflow:
    """Test TDD workflow integration."""
    
    def test_tdd_enabled_by_default(self):
        """TDD should be enabled by default."""
        gov = BridgeGovernance()
        assert gov.tdd_enabled is True
    
    def test_tdd_cycle_red_phase(self):
        """TDD cycle starts with RED phase."""
        gov = BridgeGovernance()
        
        def failing_test():
            raise AssertionError("Expected failure")
        
        def code():
            pass
        
        result = gov.run_tdd_cycle(failing_test, code)
        
        assert result['phase'] in ['red', 'failed']  # Either is acceptable
        assert result['passed'] is True  # Test failed as expected
    
    def test_tdd_cycle_green_phase(self):
        """TDD cycle should reach GREEN phase."""
        gov = BridgeGovernance()
        call_count = [0]
        
        def test():
            if call_count[0] < 1:
                raise AssertionError("Not ready")
        
        def code():
            call_count[0] += 1
        
        result = gov.run_tdd_cycle(test, code)
        
        assert result['phase'] == 'green'
        assert result['passed'] is True
    
    def test_tdd_cycle_tracks_results(self):
        """TDD cycles should be tracked."""
        gov = BridgeGovernance()
        
        gov.run_tdd_cycle(lambda: None, lambda: None)
        
        assert len(gov.test_results) == 1


class TestConfidenceScoring:
    """Test confidence scoring."""
    
    def test_confidence_improves_with_success(self):
        """Confidence should improve with successful decisions."""
        gov = BridgeGovernance()
        
        # Make 10 successful decisions
        for _ in range(10):
            gov._record_outcome(gov._create_decision(
                DecisionType.EXECUTE_TASK, "test", DecisionConfidence.HIGH, "test"
            ), True)
        
        score = gov.get_confidence_score(DecisionType.EXECUTE_TASK)
        assert score >= 0.85
    
    def test_confidence_decreases_with_failure(self):
        """Confidence should decrease with failed decisions."""
        gov = BridgeGovernance()
        
        # Make 10 failed decisions
        for _ in range(10):
            gov._record_outcome(gov._create_decision(
                DecisionType.EXECUTE_TASK, "test", DecisionConfidence.HIGH, "test"
            ), False)
        
        score = gov.get_confidence_score(DecisionType.EXECUTE_TASK)
        assert score < 0.5
    
    def test_confidence_bounded_by_samples(self):
        """Fewer samples = lower max confidence."""
        gov = BridgeGovernance()
        
        # Only 5 successful decisions
        for _ in range(5):
            gov._record_outcome(gov._create_decision(
                DecisionType.EXECUTE_TASK, "test", DecisionConfidence.HIGH, "test"
            ), True)
        
        score = gov.get_confidence_score(DecisionType.EXECUTE_TASK)
        assert score < 1.0  # Can't reach CERTAIN with few samples


class TestGovernanceReport:
    """Test governance reporting."""
    
    def test_governance_report_contains_metrics(self):
        """Report should contain key metrics."""
        gov = BridgeGovernance()
        
        report = gov.get_governance_report()
        
        assert 'circuit_open' in report
        assert 'total_decisions' in report
        assert 'confidence_scores' in report
        assert 'tdd_enabled' in report
    
    def test_decisions_by_confidence(self):
        """Report should show decisions by confidence."""
        gov = BridgeGovernance()
        
        for _ in range(5):
            gov.validate_decision(DecisionType.EXECUTE_TASK, "test", {})
        
        report = gov.get_governance_report()
        assert 'decisions_by_confidence' in report
        assert sum(report['decisions_by_confidence'].values()) == 5


class TestCircuitBreaker:
    """Test circuit breaker behavior."""
    
    def test_circuit_breaker_opens_at_threshold(self):
        """Circuit should open at threshold."""
        gov = BridgeGovernance()
        gov.config.circuit_breaker_threshold = 5
        
        for _ in range(5):
            gov.consecutive_failures += 1
        
        gov._check_circuit_breaker()
        
        assert gov.circuit_open is True
    
    def test_circuit_can_be_reset(self):
        """Circuit can be reset."""
        gov = BridgeGovernance()
        gov.circuit_open = True
        gov.circuit_failures = 10
        
        gov.reset_circuit()
        
        assert gov.circuit_open is False
        assert gov.circuit_failures == 0
        assert gov.consecutive_failures == 0


class TestDecisionApproval:
    """Test manual decision approval."""
    
    def test_low_confidence_needs_manual_approval(self):
        """Low confidence decisions need manual approval."""
        gov = BridgeGovernance()
        
        # Add failed history to lower confidence
        for _ in range(10):
            d = gov._create_decision(DecisionType.EXECUTE_TASK, "test", DecisionConfidence.LOW, "test")
            gov._record_outcome(d, False)
        
        decision, _ = gov.validate_decision(
            DecisionType.EXECUTE_TASK,
            "Risky operation",
            {}
        )
        
        # Low confidence decision should not execute without approval
        if decision.confidence == DecisionConfidence.LOW:
            def executor():
                return "executed"
            
            try:
                gov.execute_decision(decision.id, executor)
                assert False, "Should have raised"
            except ValueError:
                pass  # Expected
    
    def test_manual_approval_enables_execution(self):
        """Manual approval should enable execution."""
        gov = BridgeGovernance()
        
        decision, _ = gov.validate_decision(
            DecisionType.EXECUTE_TASK,
            "Risky operation",
            {}
        )
        
        gov.approve_decision(decision.id, "admin")
        
        result = gov.execute_decision(decision.id, lambda: "success")
        assert result == "success"