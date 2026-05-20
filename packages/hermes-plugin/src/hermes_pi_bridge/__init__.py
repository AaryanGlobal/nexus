"""
Hermes-Pi Bridge Plugin
======================

Enables Hermes to delegate tasks to pi and receive results.
Uses Hermes' existing Kanban system for task tracking.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hermes_cli.plugins import PluginContext

logger = logging.getLogger(__name__)

# Plugin metadata
__version__ = "1.0.0"


def register(ctx: "PluginContext") -> None:
    """
    Register the Hermes-Pi Bridge plugin with Hermes.

    This function is called by Hermes when loading the plugin.
    It registers tools and hooks for pi communication.
    """
    from .config import BridgeConfig
    from .tools.delegate import PiDelegateTool
    from .tools.result import PiResultTool
    from .tools.status import PiStatusTool

    # Load configuration
    config = BridgeConfig.from_context(ctx)

    # Register tools
    ctx.register_tool(PiDelegateTool(config))
    ctx.register_tool(PiStatusTool(config))
    ctx.register_tool(PiResultTool(config))

    # Register hooks
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("on_session_end", _on_session_end)

    logger.info(f"Hermes-Pi Bridge v{__version__} registered")


async def _on_session_start(session_id: str, **kwargs) -> None:
    """Called when a Hermes session starts."""
    logger.debug(f"Bridge: session started: {session_id}")


async def _on_session_end(session_id: str, **kwargs) -> None:
    """Called when a Hermes session ends."""
    logger.debug(f"Bridge: session ended: {session_id}")
    # Clean up any pending tasks for this session
    # (implemented in kanban integration)
