"""TDD: CLI Tests"""
import pytest
import subprocess
import sys
from pathlib import Path

# Get the root of the monorepo (parent of packages/core/tests is packages/core, parent is packages, parent is root)
MONOREPO_ROOT = Path(__file__).parent.parent.parent.parent
CLI_PATH = MONOREPO_ROOT / "nexus"


class TestCLI:
    """Test CLI commands."""
    
    def test_cli_exists(self):
        """CLI should exist."""
        assert CLI_PATH.exists(), f"CLI not found at {CLI_PATH}"
    
    def test_status_command(self):
        """Status command should work."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "status"],
            capture_output=True,
            text=True,
            cwd=str(MONOREPO_ROOT)
        )
        
        assert result.returncode == 0
        assert "NEXUS DASHBOARD" in result.stdout or "STATUS" in result.stdout
    
    def test_goals_command(self):
        """Goals command should work."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "goals"],
            capture_output=True,
            text=True,
            cwd=str(MONOREPO_ROOT)
        )
        
        assert result.returncode == 0
        assert "GOALS" in result.stdout
    
    def test_suggest_command(self):
        """Suggest command should work."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "suggest"],
            capture_output=True,
            text=True,
            cwd=str(MONOREPO_ROOT)
        )
        
        assert result.returncode == 0
        assert "AI SUGGESTIONS" in result.stdout
    
    def test_governance_command(self):
        """Governance command should work."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "governance"],
            capture_output=True,
            text=True,
            cwd=str(MONOREPO_ROOT)
        )
        
        assert result.returncode == 0
        assert "GOVERNANCE" in result.stdout
    
    def test_rl_command(self):
        """RL command should work."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "rl"],
            capture_output=True,
            text=True,
            cwd=str(MONOREPO_ROOT)
        )
        
        assert result.returncode == 0
        assert "RL STATISTICS" in result.stdout
    
    def test_ideate_command(self):
        """Ideate command should work."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "ideate", "[HIGH] Test goal"],
            capture_output=True,
            text=True,
            cwd=str(MONOREPO_ROOT)
        )
        
        assert result.returncode == 0
        assert "Added" in result.stdout
    
    def test_help_command(self):
        """Help should show without command."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH)],
            capture_output=True,
            text=True,
            cwd=str(MONOREPO_ROOT)
        )
        
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "Commands:" in result.stdout