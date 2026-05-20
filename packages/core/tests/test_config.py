"""TDD: Nexus Configuration Tests"""
import pytest
import tempfile
import os
import json
from pathlib import Path

from hermes_pi_bridge_core.config import (
    NexusConfig, RateLimitConfig, ScannerConfig, GovernanceConfig,
    RLConfig, StorageConfig, get_config, reset_config
)


class TestRateLimitConfig:
    """Test rate limit config."""
    
    def test_defaults(self):
        """Has sensible defaults."""
        config = RateLimitConfig()
        assert config.requests_per_minute == 30
        assert config.requests_per_hour == 500
    
    def test_validation_errors(self):
        """Validates properly."""
        config = RateLimitConfig(requests_per_minute=0)
        errors = config.validate()
        assert len(errors) > 0
        
        config = RateLimitConfig(requests_per_hour=5, requests_per_minute=10)
        errors = config.validate()
        assert any("requests_per_hour" in e for e in errors)
    
    def test_custom_values(self):
        """Accepts custom values."""
        config = RateLimitConfig(
            requests_per_minute=60,
            requests_per_hour=2000,
            burst_limit=20
        )
        assert config.requests_per_minute == 60
        assert config.burst_limit == 20


class TestScannerConfig:
    """Test scanner config."""
    
    def test_defaults(self):
        """Has sensible defaults."""
        config = ScannerConfig()
        assert config.scan_interval_seconds == 300
        assert config.enable_auto_scan is True
    
    def test_validation(self):
        """Validates properly."""
        config = ScannerConfig(scan_interval_seconds=5)
        errors = config.validate()
        assert any("scan_interval" in e for e in errors)


class TestGovernanceConfig:
    """Test governance config."""
    
    def test_defaults(self):
        """Has sensible defaults."""
        config = GovernanceConfig()
        assert config.min_confidence == 0.7
        assert config.enable_tdd is True
    
    def test_validation(self):
        """Validates confidence range."""
        config = GovernanceConfig(min_confidence=1.5)
        errors = config.validate()
        assert len(errors) > 0


class TestRLConfig:
    """Test RL config."""
    
    def test_defaults(self):
        """Has sensible defaults."""
        config = RLConfig()
        assert config.learning_rate == 0.1
        assert config.exploration_rate == 0.2
    
    def test_validation(self):
        """Validates ranges."""
        config = RLConfig(learning_rate=2.0)
        errors = config.validate()
        assert len(errors) > 0


class TestStorageConfig:
    """Test storage config."""
    
    def test_get_path(self):
        """Builds paths correctly."""
        config = StorageConfig(base_path="~/.test")
        path = config.get_path("test.json")
        assert "test.json" in str(path)


class TestNexusConfig:
    """Test main config."""
    
    def test_defaults(self):
        """Has all sub-configs."""
        config = NexusConfig()
        assert config.rate_limit is not None
        assert config.scanner is not None
        assert config.governance is not None
        assert config.rl is not None
    
    def test_validate_all(self):
        """Validates all sub-configs."""
        config = NexusConfig()
        errors = config.validate()
        assert len(errors) == 0  # All should be valid with defaults
    
    def test_get_status(self):
        """Returns status dict."""
        config = NexusConfig()
        status = config.get_status()
        assert "rate_limit" in status
        assert "scanner" in status
        assert "rl" in status


class TestConfigFromEnv:
    """Test loading from environment."""
    
    def test_loads_from_env(self):
        """Loads values from environment."""
        os.environ["NEXUS_RATE_PER_MIN"] = "50"
        os.environ["NEXUS_EXPLORATION"] = "0.3"
        
        config = NexusConfig.from_env()
        assert config.rate_limit.requests_per_minute == 50
        assert config.rl.exploration_rate == 0.3
        
        # Clean up
        del os.environ["NEXUS_RATE_PER_MIN"]
        del os.environ["NEXUS_EXPLORATION"]


class TestConfigFromFile:
    """Test loading from file."""
    
    def test_loads_from_json(self):
        """Loads from JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "rate_limit": {"requests_per_minute": 100},
                "rl": {"exploration_rate": 0.5}
            }, f)
            path = f.name
        
        config = NexusConfig.from_file(path)
        assert config.rate_limit.requests_per_minute == 100
        assert config.rl.exploration_rate == 0.5
        
        Path(path).unlink()
    
    def test_missing_file(self):
        """Handles missing file with defaults."""
        config = NexusConfig.from_file("/nonexistent/config.json")
        assert config.rate_limit.requests_per_minute == 30  # Default


class TestConfigToFile:
    """Test saving to file."""
    
    def test_saves_to_json(self):
        """Saves to JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            config = NexusConfig()
            config.rate_limit.requests_per_minute = 75
            
            config.to_file(path)
            
            # Verify
            assert path.exists()
            loaded = NexusConfig.from_file(path)
            assert loaded.rate_limit.requests_per_minute == 75


class TestGlobalConfig:
    """Test global config singleton."""
    
    def test_get_config(self):
        """Returns singleton."""
        reset_config()
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2
    
    def test_reset_config(self):
        """Can reset for testing."""
        config1 = get_config()
        reset_config()
        config2 = get_config()
        assert config1 is not config2