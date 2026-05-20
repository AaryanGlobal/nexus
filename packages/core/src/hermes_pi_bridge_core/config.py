"""
Nexus Configuration - Centralized, validated, environment-aware config
No hardcoded values - everything configurable
"""
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import os
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    requests_per_minute: int = 30
    requests_per_hour: int = 500
    requests_per_day: int = 5000
    burst_limit: int = 10
    burst_window_seconds: int = 5
    backoff_base_seconds: int = 60
    max_backoff_seconds: int = 3600
    
    def validate(self) -> list[str]:
        """Validate config, return list of errors."""
        errors = []
        if self.requests_per_minute < 1:
            errors.append("requests_per_minute must be >= 1")
        if self.requests_per_hour < self.requests_per_minute:
            errors.append("requests_per_hour must be >= requests_per_minute")
        if self.burst_limit < 1:
            errors.append("burst_limit must be >= 1")
        if self.backoff_base_seconds < 1:
            errors.append("backoff_base_seconds must be >= 1")
        return errors


@dataclass
class ScannerConfig:
    """Work scanner configuration."""
    scan_interval_seconds: int = 300
    max_tasks_per_scan: int = 50
    enable_auto_scan: bool = True
    
    def validate(self) -> list[str]:
        errors = []
        if self.scan_interval_seconds < 10:
            errors.append("scan_interval_seconds must be >= 10")
        return errors


@dataclass
class GovernanceConfig:
    """Governance configuration."""
    min_confidence: float = 0.7
    max_retries: int = 3
    circuit_breaker_threshold: int = 5
    enable_tdd: bool = True
    
    def validate(self) -> list[str]:
        errors = []
        if not 0 <= self.min_confidence <= 1:
            errors.append("min_confidence must be 0-1")
        if self.max_retries < 0:
            errors.append("max_retries must be >= 0")
        return errors


@dataclass
class RLConfig:
    """Reinforcement learning configuration."""
    learning_rate: float = 0.1
    discount_factor: float = 0.9
    exploration_rate: float = 0.2
    min_exploration: float = 0.05
    
    def validate(self) -> list[str]:
        errors = []
        if not 0 <= self.learning_rate <= 1:
            errors.append("learning_rate must be 0-1")
        if not 0 <= self.discount_factor <= 1:
            errors.append("discount_factor must be 0-1")
        if not 0 <= self.exploration_rate <= 1:
            errors.append("exploration_rate must be 0-1")
        return errors


@dataclass
class StorageConfig:
    """Storage paths configuration."""
    base_path: str = "~/.nexus"
    state_file: str = "state.json"
    goals_file: str = "goals.json"
    life_context_file: str = "life_context.json"
    log_file: str = "nexus.log"
    
    def get_path(self, filename: str) -> Path:
        """Get full path for a file."""
        return Path(self.base_path).expanduser() / filename
    
    def validate(self) -> list[str]:
        errors = []
        if not self.base_path:
            errors.append("base_path cannot be empty")
        return errors


@dataclass
class NexusConfig:
    """Main Nexus configuration - everything in one place."""
    
    # Sub-configs
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    governance: GovernanceConfig = field(default_factory=GovernanceConfig)
    rl: RLConfig = field(default_factory=RLConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    
    # Version for migration
    version: str = "1.0"
    
    @classmethod
    def from_env(cls) -> "NexusConfig":
        """Load configuration from environment variables."""
        config = cls()
        
        # Rate limit config
        if v := os.environ.get("NEXUS_RATE_PER_MIN"):
            config.rate_limit.requests_per_minute = int(v)
        if v := os.environ.get("NEXUS_RATE_PER_HOUR"):
            config.rate_limit.requests_per_hour = int(v)
        if v := os.environ.get("NEXUS_BURST_LIMIT"):
            config.rate_limit.burst_limit = int(v)
            
        # Scanner config
        if v := os.environ.get("NEXUS_SCAN_INTERVAL"):
            config.scanner.scan_interval_seconds = int(v)
            
        # Governance config
        if v := os.environ.get("NEXUS_MIN_CONFIDENCE"):
            config.governance.min_confidence = float(v)
        if v := os.environ.get("NEXUS_MAX_RETRIES"):
            config.governance.max_retries = int(v)
            
        # RL config
        if v := os.environ.get("NEXUS_LEARNING_RATE"):
            config.rl.learning_rate = float(v)
        if v := os.environ.get("NEXUS_EXPLORATION"):
            config.rl.exploration_rate = float(v)
            
        # Storage config
        if v := os.environ.get("NEXUS_BASE_PATH"):
            config.storage.base_path = v
            
        return config
    
    @classmethod
    def from_file(cls, path: str | Path) -> "NexusConfig":
        """Load configuration from JSON file."""
        path = Path(path)
        if not path.exists():
            logger.warning(f"Config file not found: {path}, using defaults")
            return cls()
            
        try:
            with open(path) as f:
                data = json.load(f)
                
            config = cls()
            
            # Load rate limit
            if rl := data.get("rate_limit", {}):
                for key in ["requests_per_minute", "requests_per_hour", "requests_per_day",
                           "burst_limit", "burst_window_seconds", "backoff_base_seconds", "max_backoff_seconds"]:
                    if key in rl:
                        setattr(config.rate_limit, key, rl[key])
            
            # Load scanner
            if sc := data.get("scanner", {}):
                for key in ["scan_interval_seconds", "max_tasks_per_scan", "enable_auto_scan"]:
                    if key in sc:
                        setattr(config.scanner, key, sc[key])
            
            # Load governance
            if gov := data.get("governance", {}):
                for key in ["min_confidence", "max_retries", "circuit_breaker_threshold", "enable_tdd"]:
                    if key in gov:
                        setattr(config.governance, key, gov[key])
            
            # Load RL
            if rl_cfg := data.get("rl", {}):
                for key in ["learning_rate", "discount_factor", "exploration_rate", "min_exploration"]:
                    if key in rl_cfg:
                        setattr(config.rl, key, rl_cfg[key])
            
            # Load storage
            if st := data.get("storage", {}):
                for key in ["base_path", "state_file", "goals_file", "life_context_file", "log_file"]:
                    if key in st:
                        setattr(config.storage, key, st[key])
            
            if v := data.get("version"):
                config.version = v
                
            return config
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error loading config: {e}, using defaults")
            return cls()
    
    def to_file(self, path: str | Path):
        """Save configuration to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "version": self.version,
            "rate_limit": {
                "requests_per_minute": self.rate_limit.requests_per_minute,
                "requests_per_hour": self.rate_limit.requests_per_hour,
                "requests_per_day": self.rate_limit.requests_per_day,
                "burst_limit": self.rate_limit.burst_limit,
                "burst_window_seconds": self.rate_limit.burst_window_seconds,
                "backoff_base_seconds": self.rate_limit.backoff_base_seconds,
                "max_backoff_seconds": self.rate_limit.max_backoff_seconds,
            },
            "scanner": {
                "scan_interval_seconds": self.scanner.scan_interval_seconds,
                "max_tasks_per_scan": self.scanner.max_tasks_per_scan,
                "enable_auto_scan": self.scanner.enable_auto_scan,
            },
            "governance": {
                "min_confidence": self.governance.min_confidence,
                "max_retries": self.governance.max_retries,
                "circuit_breaker_threshold": self.governance.circuit_breaker_threshold,
                "enable_tdd": self.governance.enable_tdd,
            },
            "rl": {
                "learning_rate": self.rl.learning_rate,
                "discount_factor": self.rl.discount_factor,
                "exploration_rate": self.rl.exploration_rate,
                "min_exploration": self.rl.min_exploration,
            },
            "storage": {
                "base_path": self.storage.base_path,
                "state_file": self.storage.state_file,
                "goals_file": self.storage.goals_file,
                "life_context_file": self.storage.life_context_file,
                "log_file": self.storage.log_file,
            },
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def validate(self) -> list[str]:
        """Validate entire config, return all errors."""
        errors = []
        errors.extend(self.rate_limit.validate())
        errors.extend(self.scanner.validate())
        errors.extend(self.governance.validate())
        errors.extend(self.rl.validate())
        errors.extend(self.storage.validate())
        return errors
    
    def get_status(self) -> dict:
        """Get config as status dict."""
        return {
            "version": self.version,
            "rate_limit": {
                "per_minute": self.rate_limit.requests_per_minute,
                "per_hour": self.rate_limit.requests_per_hour,
            },
            "scanner": {
                "interval_seconds": self.scanner.scan_interval_seconds,
            },
            "governance": {
                "min_confidence": self.governance.min_confidence,
                "max_retries": self.governance.max_retries,
            },
            "rl": {
                "learning_rate": self.rl.learning_rate,
                "exploration": self.rl.exploration_rate,
            },
            "storage": {
                "base_path": self.storage.base_path,
            },
        }


# Global config instance
_config: Optional[NexusConfig] = None


def get_config() -> NexusConfig:
    """Get global config instance (loads from env + file)."""
    global _config
    if _config is None:
        _config = NexusConfig.from_env()
        
        # Try to load from default config file
        default_config_path = Path("~/.nexus/config.json").expanduser()
        if default_config_path.exists():
            _config = NexusConfig.from_file(default_config_path)
        
        # Validate
        errors = _config.validate()
        if errors:
            logger.warning(f"Config validation errors: {errors}")
    
    return _config


def reset_config():
    """Reset global config (for testing)."""
    global _config
    _config = None