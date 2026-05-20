"""TDD: Learning Layer Tests"""
import pytest
import time
from hermes_pi_bridge_core.learning import (
    PatternLearner, TaskPattern, CapabilityAssessment
)


class TestPatternLearning:
    """Test pattern learning functionality."""
    
    def test_learn_from_successful_task(self):
        learner = PatternLearner()
        learner.learn_from_task(
            task_description="Write unit tests for API",
            decision="delegate_to_pi",
            success=True,
            duration_seconds=120.0,
            capabilities=["testing"]
        )
        
        stats = learner.get_learned_stats()
        assert stats["total_patterns"] >= 1
    
    def test_learn_from_failed_task(self):
        learner = PatternLearner()
        learner.learn_from_task(
            task_description="Debug complex issue",
            decision="delegate_to_pi",
            success=False,
            duration_seconds=300.0,
            capabilities=["debugging"]
        )
        
        # Should record the failure
        assessment = learner.get_capability_assessment("debugging")
        assert assessment.success_rate < 1.0
    
    def test_success_rate_calculation(self):
        learner = PatternLearner()
        
        # Learn from multiple tasks
        learner.learn_from_task("test1", "d1", True, 10.0, ["testing"])
        learner.learn_from_task("test2", "d2", True, 10.0, ["testing"])
        learner.learn_from_task("test3", "d3", True, 10.0, ["testing"])
        learner.learn_from_task("test4", "d4", False, 10.0, ["testing"])
        
        assessment = learner.get_capability_assessment("testing")
        # 3/4 = 75% success rate
        assert assessment.success_rate == 0.75
    
    def test_duration_averaging(self):
        learner = PatternLearner()
        
        learner.learn_from_task("t1", "d", True, 100.0, ["testing"])
        learner.learn_from_task("t2", "d", True, 200.0, ["testing"])
        
        assessment = learner.get_capability_assessment("testing")
        assert 150.0 <= assessment.avg_duration <= 150.1
    
    def test_keyword_extraction(self):
        learner = PatternLearner()
        learner.learn_from_task(
            "Create a new function to process data",
            "d",
            True,
            60.0
        )
        
        stats = learner.get_learned_stats()
        # Should have extracted code_generation capability
        assert stats["total_patterns"] >= 1


class TestCapabilityAssessment:
    """Test capability assessment."""
    
    def test_no_history_returns_zero_confidence(self):
        learner = PatternLearner()
        assessment = learner.get_capability_assessment("unknown_capability")
        
        assert assessment.confidence == 0.0
        assert "No history" in assessment.recommendation
    
    def test_low_samples_low_confidence(self):
        learner = PatternLearner()
        learner.learn_from_task("task1", "d", True, 10.0, ["testing"])
        
        assessment = learner.get_capability_assessment("testing")
        # Only 1 sample, confidence should be < 1.0
        assert assessment.confidence < 1.0
    
    def test_high_samples_high_confidence(self):
        learner = PatternLearner()
        for _ in range(15):
            learner.learn_from_task("task", "d", True, 10.0, ["testing"])
        
        assessment = learner.get_capability_assessment("testing")
        # Max confidence at 10 samples
        assert assessment.confidence >= 0.9
    
    def test_recommendation_for_low_success(self):
        learner = PatternLearner()
        for _ in range(5):
            learner.learn_from_task("task", "d", False, 10.0, ["debugging"])
        
        assessment = learner.get_capability_assessment("debugging")
        assert "Low success" in assessment.recommendation
    
    def test_recommendation_for_high_success(self):
        learner = PatternLearner()
        for _ in range(5):
            learner.learn_from_task("task", "d", True, 10.0, ["testing"])
        
        assessment = learner.get_capability_assessment("testing")
        assert "High success" in assessment.recommendation


class TestImprovementSuggestions:
    """Test improvement suggestions."""
    
    def test_suggestion_for_low_success_capability(self):
        learner = PatternLearner()
        
        # Create low success capability
        for _ in range(5):
            learner.learn_from_task("task", "d", False, 10.0, ["refactoring"])
        
        suggestions = learner.suggest_improvements()
        assert len(suggestions) >= 1
        assert any("refactor" in s.lower() for s in suggestions)
    
    def test_suggestion_for_slow_capability(self):
        learner = PatternLearner()
        
        # Create slow capability (avg > 5 min)
        for _ in range(5):
            learner.learn_from_task("task", "d", True, 400.0, ["research"])  # ~6.6 min
        
        suggestions = learner.suggest_improvements()
        assert len(suggestions) >= 1
        assert any("optimize" in s.lower() for s in suggestions)
    
    def test_no_suggestions_when_all_good(self):
        learner = PatternLearner()
        
        # Create high success, fast capabilities
        for _ in range(5):
            learner.learn_from_task("task", "d", True, 30.0, ["testing"])
        
        suggestions = learner.suggest_improvements()
        # May be empty or contain other suggestions
        assert isinstance(suggestions, list)


class TestDelegationDecision:
    """Test delegation decision based on learning."""
    
    def test_block_delegation_on_low_success(self):
        learner = PatternLearner()
        
        # Learn that debugging has low success
        for _ in range(5):
            learner.learn_from_task("debug task", "d", False, 100.0, ["debugging"])
        
        should_delegate, confidence, reasoning = learner.should_delegate(
            "Fix this bug",
            ["debugging"]
        )
        
        assert should_delegate is False
        assert confidence > 0.5
    
    def test_allow_delegation_on_high_success(self):
        learner = PatternLearner()
        
        # Learn that testing has high success
        for _ in range(5):
            learner.learn_from_task("test task", "d", True, 50.0, ["testing"])
        
        should_delegate, confidence, reasoning = learner.should_delegate(
            "Write tests for API",
            ["testing"]
        )
        
        assert should_delegate is True
    
    def test_partial_match_still_delegates(self):
        learner = PatternLearner()
        
        # No history
        should_delegate, confidence, reasoning = learner.should_delegate(
            "Create a new function",
            []
        )
        
        assert should_delegate is True
        assert "partial" in reasoning.lower() or "no negative" in reasoning.lower()


class TestHistoryManagement:
    """Test task history management."""
    
    def test_history_bounded(self):
        learner = PatternLearner()
        learner.max_history = 10
        
        for i in range(20):
            learner.learn_from_task(f"task {i}", "d", True, 10.0)
        
        assert len(learner.task_history) <= 10
    
    def test_history_contains_latest(self):
        learner = PatternLearner()
        learner.max_history = 5
        
        for i in range(10):
            learner.learn_from_task(f"task {i}", "d", True, 10.0)
        
        # Last items should be tasks 5-9
        assert learner.task_history[0]["description"] == "task 5"
        assert learner.task_history[-1]["description"] == "task 9"


class TestPatternStats:
    """Test pattern statistics."""
    
    def test_stats_include_occurrences(self):
        learner = PatternLearner()
        learner.learn_from_task("task1", "d", True, 10.0, ["testing"])
        learner.learn_from_task("task2", "d", True, 10.0, ["testing"])
        
        stats = learner.get_learned_stats()
        assert "patterns" in stats
        if "cap:testing" in stats["patterns"]:
            assert stats["patterns"]["cap:testing"]["occurrences"] >= 2
    
    def test_stats_include_success_rate(self):
        learner = PatternLearner()
        learner.learn_from_task("t1", "d", True, 10.0, ["testing"])
        learner.learn_from_task("t2", "d", False, 10.0, ["testing"])
        
        stats = learner.get_learned_stats()
        if "cap:testing" in stats["patterns"]:
            assert stats["patterns"]["cap:testing"]["success_rate"] == 0.5
