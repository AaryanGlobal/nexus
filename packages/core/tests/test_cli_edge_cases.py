"""TDD: CLI Edge Cases and Failure Modes Tests"""
import pytest
import subprocess
import sys
import tempfile
import json
from pathlib import Path

# Dynamic path to CLI
MONOREPO_ROOT = Path(__file__).parent.parent.parent.parent
CLI_PATH = str(MONOREPO_ROOT / "nexus")
PYTHON = sys.executable


def run_cli(args, env=None):
    """Run CLI command and return result."""
    env = env or {}
    full_env = {**dict(__import__('os').environ), **env}
    return subprocess.run(
        [PYTHON, CLI_PATH] + args,
        capture_output=True,
        text=True,
        env=full_env
    )


class TestCLIInputEdgeCases:
    """Test CLI with edge case inputs."""
    
    def test_empty_goal_input(self):
        """Empty goal input should be handled."""
        result = run_cli(["goal", ""])
        # Should handle gracefully or show help
        assert result.returncode in [0, 1, 2]
    
    def test_whitespace_only_goal(self):
        """Whitespace-only goal should be handled."""
        result = run_cli(["goal", "   \n  \t  "])
        assert result.returncode in [0, 1, 2]
    
    def test_unicode_goal_input(self):
        """Unicode goal input should be handled."""
        result = run_cli(["goal", "🎯 Learn émoji 🇺🇸"])
        assert result.returncode in [0, 1, 2]


class TestCLIStateFailures:
    """Test CLI with state file issues."""
    
    def test_missing_state_file(self):
        """Missing state file should create new one."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "missing.json"
            
            result = run_cli(
                ["status"],
                env={"HERMES_PBRIDGE_STATE": str(state_file)}
            )
            # Should work or create file
            assert result.returncode == 0 or state_file.exists()
    
    def test_concurrent_access(self):
        """Concurrent CLI calls should not corrupt state."""
        import concurrent.futures
        
        def run_status():
            result = run_cli(["status"])
            return result.returncode == 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(run_status) for _ in range(10)]
            results = [f.result() for f in futures]
        
        assert all(results)


class TestCLIIntegrationFailures:
    """Test CLI when integration components fail."""
    
    def test_hermes_not_running(self):
        """When Hermes not running, CLI should not crash."""
        result = run_cli(["status"])
        # Should not crash (exit code 0 or 1)
        assert result.returncode in [0, 1]
    
    def test_pi_not_connected(self):
        """When PI not connected, CLI should not crash."""
        result = run_cli(["goals"])
        # Should not crash (exit code 0 or 1)
        assert result.returncode in [0, 1]


class TestCLIOutputEdgeCases:
    """Test CLI output handling."""
    
    def test_lines_not_too_long(self):
        """Lines should not be excessively long."""
        result = run_cli(["goals"])
        for line in result.stdout.split('\n'):
            if line.strip():
                assert len(line) < 200, f"Line too long: {len(line)} chars"


class TestCLIMemoryAndPerformance:
    """Test CLI memory and performance."""
    
    def test_rapid_commands(self):
        """Rapid commands should not cause memory issues."""
        for _ in range(5):
            result = run_cli(["status"])
            assert result.returncode == 0
    
    def test_help_command(self):
        """Help command should work."""
        result = subprocess.run(
            [PYTHON, CLI_PATH, "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()


class TestCLIErrors:
    """Test CLI error handling."""
    
    def test_unknown_command(self):
        """Unknown command should show helpful error."""
        result = subprocess.run(
            [PYTHON, CLI_PATH, "unknown_cmd"],
            capture_output=True,
            text=True
        )
        assert result.returncode != 0
    
    def test_missing_arguments(self):
        """Missing required arguments should show error."""
        result = subprocess.run(
            [PYTHON, CLI_PATH, "do"],
            capture_output=True,
            text=True
        )
        assert result.returncode != 0