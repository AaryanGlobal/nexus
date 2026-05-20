"""
Self-Evolution Layer for Hermes-Pi Bridge

Enables the system to:
1. Execute code safely
2. Run tests and interpret results
3. Learn from failures and adapt
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TestResult:
    """Result of a test execution."""
    passed: int
    failed: int
    skipped: int
    errors: int
    total: int
    duration_seconds: float
    output: str
    success: bool
    
    @classmethod
    def from_pytest_output(cls, output: str, duration: float) -> 'TestResult':
        """Parse pytest JSON output if available, otherwise parse text."""
        try:
            data = json.loads(output)
            return cls(
                passed=data.get('passed', 0),
                failed=data.get('failed', 0),
                skipped=data.get('skipped', 0),
                errors=data.get('errors', 0),
                total=data.get('total', 0),
                duration_seconds=duration,
                output=output,
                success=data.get('success', False)
            )
        except (json.JSONDecodeError, TypeError):
            return cls._parse_text_output(output, duration)
    
    @classmethod
    def _parse_text_output(cls, output: str, duration: float) -> 'TestResult':
        """Parse pytest text output."""
        passed = failed = skipped = errors = 0
        
        for line in output.split('\n'):
            failed_match = re.search(r'(\d+)\s+failed', line)
            passed_match = re.search(r'(\d+)\s+passed', line)
            if failed_match:
                failed = int(failed_match.group(1))
            if passed_match:
                passed = int(passed_match.group(1))
        
        total = passed + failed + skipped + errors
        return cls(
            passed=passed, failed=failed, skipped=skipped, errors=errors,
            total=total, duration_seconds=duration,
            output=output[:5000], success=failed == 0 and errors == 0
        )


@dataclass
class EvolutionRecord:
    """Record of an evolution attempt."""
    timestamp: float
    trigger: str  # What caused the evolution attempt
    action: str    # What was attempted
    test_results: TestResult | None
    success: bool
    artifacts: dict[str, Any] = field(default_factory=dict)


class EvolutionController:
    """
    Controls the self-evolution loop.
    
    Evolution Loop:
    1. Detect failure/need for improvement
    2. Analyze root cause
    3. Generate potential fix
    4. Test the fix
    5. Record outcome
    6. Repeat if needed
    """
    
    def __init__(self, workspace: Path | str = "/tmp/evolution"):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.history: list[EvolutionRecord] = []
        self.max_retries = 3
    
    def run_tests(
        self,
        test_path: str,
        python_path: str = "python3",
        pytest_args: str = "-v --tb=short",
        timeout: int = 120
    ) -> TestResult:
        """Run tests and return results."""
        start_time = time.time()
        
        try:
            result = subprocess.run(
                [python_path, "-m", "pytest", test_path] + pytest_args.split(),
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace)
            )
            output = result.stdout + "\n" + result.stderr
            duration = time.time() - start_time
            
            return TestResult.from_pytest_output(output, duration)
            
        except subprocess.TimeoutExpired:
            return TestResult(
                passed=0, failed=0, skipped=0, errors=1,
                total=0, duration_seconds=timeout,
                output="Test execution timed out",
                success=False
            )
        except Exception as e:
            return TestResult(
                passed=0, failed=0, skipped=0, errors=1,
                total=0, duration_seconds=time.time() - start_time,
                output=str(e),
                success=False
            )
    
    def run_typescript_tests(
        self,
        test_path: str,
        npm_path: str = "npm",
        timeout: int = 120
    ) -> TestResult:
        """Run TypeScript tests."""
        start_time = time.time()
        
        try:
            result = subprocess.run(
                [npm_path, "test", "--", "--run", test_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace)
            )
            output = result.stdout + "\n" + result.stderr
            duration = time.time() - start_time
            
            return TestResult.from_pytest_output(output, duration)
            
        except subprocess.TimeoutExpired:
            return TestResult(
                passed=0, failed=0, skipped=0, errors=1,
                total=0, duration_seconds=timeout,
                output="Test execution timed out",
                success=False
            )
        except Exception as e:
            return TestResult(
                passed=0, failed=0, skipped=0, errors=1,
                total=0, duration_seconds=time.time() - start_time,
                output=str(e),
                success=False
            )
    
    def apply_fix(
        self,
        file_path: str | Path,
        old_content: str | None,
        new_content: str
    ) -> bool:
        """Apply a code fix to a file."""
        try:
            path = Path(file_path)
            if old_content is not None and path.exists():
                if path.read_text() != old_content:
                    return False
            path.write_text(new_content)
            return True
        except Exception:
            return False
    
    def evolve(
        self,
        trigger: str,
        action: str,
        test_path: str,
        python_path: str = "python3"
    ) -> EvolutionRecord:
        """Run one evolution cycle: action → test → record."""
        record = EvolutionRecord(
            timestamp=time.time(),
            trigger=trigger,
            action=action,
            test_results=None,
            success=False
        )
        
        # Run tests
        test_results = self.run_tests(test_path, python_path)
        record.test_results = test_results
        record.success = test_results.success
        
        # Record
        self.history.append(record)
        
        return record
    
    def get_evolution_stats(self) -> dict[str, Any]:
        """Get evolution statistics."""
        if not self.history:
            return {"total_cycles": 0, "success_rate": 0.0}
        
        total = len(self.history)
        successes = sum(1 for r in self.history if r.success)
        
        return {
            "total_cycles": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": successes / total if total > 0 else 0.0,
            "last_attempt": self.history[-1].timestamp if self.history else None,
            "last_success": next(
                (r.timestamp for r in reversed(self.history) if r.success),
                None
            )
        }
    
    def attempt_fix(
        self,
        task_description: str,
        error: str,
        test_path: str | None = None,
    ) -> EvolutionRecord:
        """Attempt to fix a failed task using evolution."""
        # Create an evolution record for this attempt
        record = EvolutionRecord(
            timestamp=time.time(),
            trigger=f"task_failure: {task_description[:50]}",
            action=f"fix_attempt: {error[:100]}",
            test_results=None,
            success=False
        )
        
        # Run tests if provided
        if test_path:
            record.test_results = self.run_tests(test_path)
            record.success = record.test_results.success if record.test_results else False
        
        self.history.append(record)
        return record
    
    def export_history(self, path: str | Path) -> bool:
        """Export evolution history to JSON."""
        try:
            data = [
                {
                    "timestamp": r.timestamp,
                    "trigger": r.trigger,
                    "action": r.action,
                    "success": r.success,
                    "test_results": {
                        "passed": r.test_results.passed if r.test_results else 0,
                        "failed": r.test_results.failed if r.test_results else 0,
                        "success": r.test_results.success if r.test_results else False
                    }
                }
                for r in self.history
            ]
            Path(path).write_text(json.dumps(data, indent=2))
            return True
        except Exception:
            return False
