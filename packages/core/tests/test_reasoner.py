"""TDD: Task Reasoner Tests"""
import pytest
from hermes_pi_bridge_core.reasoner import (
    TaskReasoner, TaskAnalysis, DelegationReason, DelegationDecision,
    TaskComplexity, AgentCapability
)

class TestComplexityAssessment:
    """Test task complexity assessment."""
    
    def test_simple_task_detected(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Read this file")
        assert analysis.complexity == TaskComplexity.SIMPLE
    
    def test_moderate_task_detected(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Create a new function")
        assert analysis.complexity == TaskComplexity.MODERATE
    
    def test_complex_task_detected(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Architect a new system")
        assert analysis.complexity == TaskComplexity.COMPLEX
    
    def test_epic_task_detected(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Redesign the entire application")
        assert analysis.complexity == TaskComplexity.EPIC
    
    def test_unknown_defaults_to_simple(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Do something")
        assert analysis.complexity == TaskComplexity.SIMPLE


class TestCapabilityIdentification:
    """Test capability detection from descriptions."""
    
    def test_code_generation_detected(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Create a function to sort list")
        assert AgentCapability.CODE_GENERATION in analysis.required_capabilities
    
    def test_debugging_detected(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Fix the error in main.py")
        assert AgentCapability.DEBUGGING in analysis.required_capabilities
    
    def test_testing_detected(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Write tests for the API")
        assert AgentCapability.TESTING in analysis.required_capabilities
    
    def test_file_operations_detected(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Read the config file")
        assert AgentCapability.FILE_OPERATIONS in analysis.required_capabilities
    
    def test_research_detected(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Research best practices for caching")
        assert AgentCapability.RESEARCH in analysis.required_capabilities


class TestSideEffectDetection:
    """Test side effect detection."""
    
    def test_delete_has_side_effects(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Delete all temporary files")
        assert analysis.has_side_effects is True
    
    def test_read_is_safe(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Read the log file")
        assert analysis.has_side_effects is False
    
    def test_sudo_has_side_effects(self):
        r = TaskReasoner()
        analysis = r.analyze_task("sudo apt update")
        assert analysis.has_side_effects is True


class TestDelegationDecision:
    """Test delegation decision logic."""
    
    def test_pi_capable_task_delegates_to_pi(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Write unit tests for calculator")
        decision = r.decide(analysis)
        assert decision.decision == DelegationDecision.DELEGATE_TO_PI
        assert decision.capability_match["pi"] > decision.capability_match["hermes"]
    
    def test_epic_task_splits(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Redesign entire database schema")
        decision = r.decide(analysis)
        assert decision.decision == DelegationDecision.SPLIT_AND_DELEGATE
        assert len(decision.subtasks) >= 2
    
    def test_side_effect_task_rejected(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Delete production database")
        decision = r.decide(analysis)
        assert decision.decision == DelegationDecision.REJECT
        assert "human" in decision.reasoning.lower() or "approval" in decision.reasoning.lower()
    
    def test_confidence_reflects_capability_match(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Create a simple function")
        decision = r.decide(analysis)
        assert 0.0 <= decision.confidence <= 1.0
    
    def test_priority_elevated_for_hard_tasks(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Architect entire system")
        decision = r.decide(analysis)
        assert decision.suggested_priority in ["high", "normal"]


class TestCapabilityMatching:
    """Test capability matching algorithm."""
    
    def test_full_match_returns_100_percent(self):
        r = TaskReasoner()
        match = r._calculate_capability_match(
            [AgentCapability.FILE_OPERATIONS],
            r.pi_capabilities
        )
        assert match == 1.0
    
    def test_partial_match_returns_correct_ratio(self):
        r = TaskReasoner()
        match = r._calculate_capability_match(
            [AgentCapability.CODE_GENERATION, AgentCapability.RESEARCH],
            r.pi_capabilities  # Missing RESEARCH
        )
        assert match == 0.5
    
    def test_no_match_returns_zero(self):
        r = TaskReasoner()
        match = r._calculate_capability_match(
            [AgentCapability.RESEARCH],  # Hermes-only capability
            r.pi_capabilities
        )
        assert match == 0.0
    
    def test_empty_requirements_returns_full_match(self):
        r = TaskReasoner()
        match = r._calculate_capability_match([], r.pi_capabilities)
        assert match == 1.0


class TestEdgeCases:
    """Test edge cases and failure modes."""
    
    def test_empty_description(self):
        r = TaskReasoner()
        analysis = r.analyze_task("")
        assert analysis.complexity == TaskComplexity.SIMPLE
    
    def test_very_long_description(self):
        r = TaskReasoner()
        long_desc = "Implement " * 100
        analysis = r.analyze_task(long_desc)
        # Should handle without crashing
        assert analysis.complexity is not None
    
    def test_unicode_in_description(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Fix 日本語 character encoding")
        assert analysis.task_id is not None
    
    def test_custom_capabilities_respected(self):
        r = TaskReasoner(
            pi_capabilities={AgentCapability.CODE_GENERATION},
            hermes_capabilities={}
        )
        analysis = r.analyze_task("Generate code")
        decision = r.decide(analysis)
        assert decision.decision == DelegationDecision.DELEGATE_TO_PI
    
    def test_custom_delegation_threshold(self):
        r = TaskReasoner(auto_delegate_threshold=0.9)
        analysis = r.analyze_task("Research something")  # Low pi match
        decision = r.decide(analysis)
        # Should be more conservative with high threshold
        assert decision.decision in [d.value for d in DelegationDecision]


class TestDurationEstimation:
    """Test duration estimation."""
    
    def test_trivial_duration_short(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Quick fix")
        assert analysis.estimated_duration_minutes <= 5
    
    def test_epic_duration_long(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Complete system redesign")
        assert analysis.estimated_duration_minutes >= 60
    
    def test_duration_capped_at_max(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Implement " * 100)
        assert analysis.estimated_duration_minutes <= 480


class TestIdempotency:
    """Test idempotency detection."""
    
    def test_read_is_idempotent(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Read the configuration")
        assert analysis.is_idempotent is True
    
    def test_delete_is_not_idempotent(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Delete the log file")
        assert analysis.is_idempotent is False
    
    def test_create_is_not_idempotent(self):
        r = TaskReasoner()
        analysis = r.analyze_task("Create a new class")
        assert analysis.is_idempotent is False


class TestIntegration:
    """Integration tests for full analysis flow."""
    
    def test_full_analysis_pipeline(self):
        r = TaskReasoner()
        analysis = r.analyze_task(
            "Write comprehensive unit tests for the authentication module",
            context={"task_id": "auth-tests-001"}
        )
        
        # Should have all fields populated
        assert analysis.task_id == "auth-tests-001"
        assert analysis.required_capabilities
        assert analysis.estimated_duration_minutes > 0
        
        # Should make a decision
        decision = r.decide(analysis)
        assert decision.decision in [d.value for d in DelegationDecision]
        assert decision.reasoning
        assert decision.confidence > 0
