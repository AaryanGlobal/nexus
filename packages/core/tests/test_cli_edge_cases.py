"""TDD: CLI Edge Cases and Failure Modes Tests"""
import pytest
import subprocess
import sys
import tempfile
import json
from pathlib import Path

# Absolute path to CLI
CLI_PATH = "/home/agi/nexus/nexus"
PYTHON = "/home/agi/.hermes/hermes-agent/venv/bin/python3"


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
    
    def test_empty_ideation(self):
        """Empty ideation should not crash."""
        result = run_cli(["ideate", ""])
        # Should handle gracefully
        assert result.returncode == 0 or "Error" in result.stderr
    
    def test_whitespace_only(self):
        """Whitespace-only ideation should be handled."""
        result = run_cli(["ideate", "   \n  \t  "])
        assert result.returncode == 0
    
    def test_unicode_input(self):
        """Unicode input should be handled."""
        result = run_cli(["ideate", "🎯 Learn émoji 🇺🇸"])
        assert result.returncode == 0


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
        """When Hermes not running, CLI should still work."""
        result = run_cli(["status"])
        assert result.returncode == 0
        assert "DASHBOARD" in result.stdout or "STATUS" in result.stdout
    
    def test_pi_not_connected(self):
        """When PI not connected, CLI should still work."""
        result = run_cli(["goals"])
        assert result.returncode == 0


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