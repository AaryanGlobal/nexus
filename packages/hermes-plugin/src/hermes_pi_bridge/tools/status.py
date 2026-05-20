"""
pi_status tool - Check pi availability.
"""

import json
import logging

from ..config import BridgeConfig
from ..transport import PiHttpClient

logger = logging.getLogger(__name__)


class PiStatusTool:
    """
    Tool to check pi agent availability and status.

    Usage in Hermes:
        /pi_status
    """

    def __init__(self, config: BridgeConfig):
        self.config = config
        self.client = PiHttpClient(
            base_url=config.pi_url,
            auth_token=config.auth_token,
        )

    @property
    def name(self) -> str:
        return "pi_status"

    @property
    def description(self) -> str:
        return """Check if pi agent is available and ready.

Returns:
- availability status
- pi version
- current workload
- max concurrent tasks

No parameters required.
"""

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {},
        }

    def execute(self, **kwargs) -> str:
        """
        Check pi status.

        Returns:
            JSON string with pi status
        """
        try:
            status = self.client.get_status()

            if status.get("available"):
                return json.dumps({
                    "ok": True,
                    "available": True,
                    "version": status.get("version", "unknown"),
                    "max_concurrent": status.get("max_concurrent", 0),
                    "current_load": status.get("current_load", 0),
                    "capabilities": status.get("capabilities", []),
                })
            else:
                return json.dumps({
                    "ok": True,
                    "available": False,
                    "reason": status.get("reason", "unknown"),
                })

        except Exception as e:
            logger.error(f"pi status check error: {e}")
            return json.dumps({
                "ok": True,
                "available": False,
                "reason": str(e),
            })
