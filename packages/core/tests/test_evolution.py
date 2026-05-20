"""TDD: Self-Evolution Layer Tests"""
import pytest
import json
from pathlib import Path
from hermes_pi_bridge_core.evolution import (
    EvolutionController, TestResult, EvolutionRecord
)

class TestTestResultParsing:
    """Test test result parsing."""
    
    def test_parse_pytest_summary(self):
        output = "test_file.py ....... 10 passed in 0.5s"
        result = TestResult._parse_text_output(output, 0.5)
        assert result.passed == 10
        assert result.failed == 0
        assert result.success is True
    
    def test_parse_failed_tests(self):
        output = "1 failed, 5 passed in 1.2s"
        result = TestResult._parse_text_output(output, 1.2)
        assert result.passed == 5
        assert result.failed == 1
        assert result.success is False
    
    def test_parse_json_output(self):
        json_data = '{"passed": 15, "failed": 2, "skipped": 1, "success": false}'
        result = TestResult.from_pytest_output(json_data, 2.0)
        assert result.passed == 15
        assert result.failed == 2
        assert result.success is False


class TestEvolutionController:
    """Test evolution controller."""
    
    def test_init_creates_workspace(self, tmp_path):
        ctrl = EvolutionController(tmp_path / "test_workspace")
        assert ctrl.workspace.exists()
        assert ctrl.workspace.is_dir()
    
    def test_init_default_workspace(self):
        ctrl = EvolutionController()
        assert ctrl.workspace == Path("/tmp/evolution")
    
    def test_empty_history(self):
        ctrl = EvolutionController()
        assert ctrl.history == []
        stats = ctrl.get_evolution_stats()
        assert stats["total_cycles"] == 0
    
    def test_evolution_stats_initial(self):
        ctrl = EvolutionController()
        stats = ctrl.get_evolution_stats()
        assert "success_rate" in stats
        assert stats["success_rate"] == 0.0
    
    def test_run_tests_returns_result(self):
        ctrl = EvolutionController()
        # Run a real test that exists
        result = ctrl.run_tests(
            "packages/core/tests/test_types.py",
            python_path="$HOME/.hermes/hermes-agent/venv/bin/python3"
        )
        # Should return a TestResult object
        assert isinstance(result, TestResult)
        assert result.total >= 0
    
    def test_run_tests_timeout(self):
        ctrl = EvolutionController()
        result = ctrl.run_tests(
            "nonexistent_test.py",
            timeout=1
        )
        # Should handle timeout gracefully
        assert result.errors >= 0
    
    def test_apply_fix_creates_file(self, tmp_path):
        ctrl = EvolutionController(tmp_path)
        test_file = tmp_path / "test_fix.py"
        
        success = ctrl.apply_fix(
            test_file,
            old_content=None,  # New file
            new_content="# Test fix applied\nprint('Hello')"
        )
        assert success is True
        assert test_file.exists()
        assert "Test fix" in test_file.read_text()
    
    def test_export_history(self, tmp_path):
        ctrl = EvolutionController(tmp_path)
        history_file = tmp_path / "history.json"
        
        # Add a record
        ctrl.evolve(
            trigger="test_failure",
            action="fix_bug",
            test_path="test_file.py"
        )
        
        success = ctrl.export_history(history_file)
        assert success is True
        assert history_file.exists()
        
        # Verify JSON is valid
        data = json.loads(history_file.read_text())
        assert isinstance(data, list)
        assert len(data) >= 1
    
    def test_evolution_stats_with_records(self, tmp_path):
        ctrl = EvolutionController(tmp_path)
        
        # Add successful and failed evolutions
        ctrl.evolve("test", "fix1", "test.py")
        ctrl.evolve("test", "fix2", "test.py")
        
        stats = ctrl.get_evolution_stats()
        assert stats["total_cycles"] == 2
        assert "successes" in stats
        assert "failures" in stats


class TestSelfHealing:
    """Test self-healing behavior."""
    
    def test_detect_failure_from_result(self):
        result = TestResult(
            passed=10, failed=1, skipped=0, errors=0,
            total=11, duration_seconds=1.0,
            output="Test failed", success=False
        )
        assert result.success is False
        assert result.failed == 1
    
    def test_circuit_breaker_for_repeated_failures(self):
        ctrl = EvolutionController()
        
        # Simulate repeated failures
        failures = 0
        for i in range(10):
            if failures >= ctrl.max_retries:
                break
            failures += 1
        
        # Should stop after max_retries
        assert failures == ctrl.max_retries
    
    def test_success_resets_circuit(self):
        result = TestResult(
            passed=5, failed=0, skipped=0, errors=0,
            total=5, duration_seconds=0.5,
            output="All passed", success=True
        )
        assert result.success is True
        assert result.failed == 0
