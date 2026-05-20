"""TDD: CLI Tests"""
import pytest
import subprocess
import sys
from pathlib import Path

# Get the root of the monorepo
MONOREPO_ROOT = Path(__file__).parent.parent.parent.parent
CLI_PATH = MONOREPO_ROOT / "nexus"


def is_server_running():
    """Check if Nexus server is running."""
    try:
        import urllib.request
        urllib.request.urlopen('http://localhost:8080/health', timeout=1)
        return True
    except Exception:
        return False


class TestCLI:
    """Test CLI commands."""
    
    def test_cli_exists(self):
        """CLI should exist."""
        assert CLI_PATH.exists(), f"CLI not found at {CLI_PATH}"
    
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
    
    @pytest.mark.skipif(not is_server_running(), reason="Server not running")
    def test_status_command(self):
        """Status command should work."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "status"],
            capture_output=True,
            text=True,
            cwd=str(MONOREPO_ROOT)
        )
        
        assert result.returncode == 0
        assert "NEXUS" in result.stdout or "Status" in result.stdout
    
    @pytest.mark.skipif(not is_server_running(), reason="Server not running")
    def test_goals_command(self):
        """Goals command should work."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "goals"],
            capture_output=True,
            text=True,
            cwd=str(MONOREPO_ROOT)
        )
        
        assert result.returncode == 0
    
    @pytest.mark.skipif(not is_server_running(), reason="Server not running")
    def test_pillars_command(self):
        """Pillars command should work."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "pillars"],
            capture_output=True,
            text=True,
            cwd=str(MONOREPO_ROOT)
        )
        
        assert result.returncode == 0
    
    @pytest.mark.skipif(not is_server_running(), reason="Server not running")
    def test_capabilities_command(self):
        """Capabilities command should work."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "capabilities"],
            capture_output=True,
            text=True,
            cwd=str(MONOREPO_ROOT)
        )
        
        assert result.returncode == 0
    
    @pytest.mark.skipif(not is_server_running(), reason="Server not running")
    def test_health_command(self):
        """Health command should work."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "health"],
            capture_output=True,
            text=True,
            cwd=str(MONOREPO_ROOT)
        )
        
        assert result.returncode == 0
    
    def test_discover_command(self):
        """Discover should run without server."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "discover"],
            capture_output=True,
            text=True,
            cwd=str(MONOREPO_ROOT)
        )
        
        # Should not crash
        assert result.returncode in [0, 1]
    
    def test_sample_command(self):
        """Sample should run without server."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "sample"],
            capture_output=True,
            text=True,
            cwd=str(MONOREPO_ROOT)
        )
        
        # Should not crash
        assert result.returncode in [0, 1]
    
    def test_sync_command(self):
        """Sync should run without server."""
        result = subprocess.run(
            [sys.executable, str(CLI_PATH), "sync"],
            capture_output=True,
            text=True,
            cwd=str(MONOREPO_ROOT)
        )
        
        # Should not crash
        assert result.returncode in [0, 1]