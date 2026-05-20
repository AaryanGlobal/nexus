"""
Configuration management for Hermes-Pi Bridge.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hermes_cli.plugins import PluginContext

# Default configuration values
DEFAULT_PI_URL = "http://localhost:2719"
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_MAX_CONCURRENT = 2
DEFAULT_AUTH_TOKEN = ""


@dataclass
class BridgeConfig:
    """Configuration for Hermes-Pi Bridge."""

    # pi HTTP server URL
    pi_url: str = DEFAULT_PI_URL

    # Authentication token (optional)
    auth_token: str = DEFAULT_AUTH_TOKEN

    # Max concurrent tasks to pi
    max_concurrent: int = DEFAULT_MAX_CONCURRENT

    # Default timeout for tasks (seconds)
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    # Hermes home directory
    hermes_home: Path = field(default_factory=lambda: Path.home() / ".hermes")

    # Kanban database path
    kanban_db: Path = field(init=False)

    def __post_init__(self):
        """Set derived paths and apply environment variable overrides."""
        self.kanban_db = self.hermes_home / "kanban.db"

        # Environment variables override dataclass defaults
        # (but not explicit constructor arguments when from_context is used)
        if os.environ.get("HERMES_PI_BRIDGE_PI_URL"):
            self.pi_url = os.environ.get("HERMES_PI_BRIDGE_PI_URL", self.pi_url)
        if os.environ.get("HERMES_PI_BRIDGE_AUTH_TOKEN"):
            self.auth_token = os.environ.get("HERMES_PI_BRIDGE_AUTH_TOKEN", self.auth_token)
        if os.environ.get("HERMES_PI_BRIDGE_MAX_CONCURRENT"):
            self.max_concurrent = int(os.environ.get("HERMES_PI_BRIDGE_MAX_CONCURRENT", self.max_concurrent))
        if os.environ.get("HERMES_PI_BRIDGE_TIMEOUT"):
            self.timeout_seconds = int(os.environ.get("HERMES_PI_BRIDGE_TIMEOUT", self.timeout_seconds))

    @classmethod
    def from_context(cls, ctx: PluginContext) -> BridgeConfig:
        """
        Create config from Hermes plugin context.

        Reads from:
        1. Environment variables (HERMES_PI_BRIDGE_*)
        2. Config file (~/.hermes/config.yaml)
        3. Defaults
        """
        # Get Hermes home from environment or context
        hermes_home = os.environ.get(
            "HERMES_HOME",
            str(Path.home() / ".hermes")
        )

        # Read from config file if available
        config_path = Path(hermes_home) / "config.yaml"
        file_config = _read_yaml_config(config_path)

        # Get bridge config section
        bridge_config = file_config.get("hermes_pi_bridge", {})

        return cls(
            pi_url=os.environ.get(
                "HERMES_PI_BRIDGE_PI_URL",
                bridge_config.get("pi_url", DEFAULT_PI_URL)
            ),
            auth_token=os.environ.get(
                "HERMES_PI_BRIDGE_AUTH_TOKEN",
                bridge_config.get("auth_token", DEFAULT_AUTH_TOKEN)
            ),
            max_concurrent=int(os.environ.get(
                "HERMES_PI_BRIDGE_MAX_CONCURRENT",
                bridge_config.get("max_concurrent", DEFAULT_MAX_CONCURRENT)
            )),
            timeout_seconds=int(os.environ.get(
                "HERMES_PI_BRIDGE_TIMEOUT",
                bridge_config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
            )),
            hermes_home=Path(hermes_home),
        )


def _read_yaml_config(path: Path) -> dict:
    """Read YAML config file, return empty dict if not found."""
    try:
        import yaml
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f) or {}
    except ImportError:
        pass  # yaml not available
    except Exception:
        pass  # Ignore other errors
    return {}
