"""
pi_result tool - Receive results from pi agent.
"""

import json
import logging

from ..config import BridgeConfig

logger = logging.getLogger(__name__)


class PiResultTool:
    """
    Tool to query results of delegated tasks.

    This is primarily for internal use by the bridge protocol.
    Users typically don't call this directly.

    Usage in Hermes:
        /pi_result task_id="uuid"
    """

    def __init__(self, config: BridgeConfig):
        self.config = config

    @property
    def name(self) -> str:
        return "pi_result"

    @property
    def description(self) -> str:
        return """Get result of a task delegated to pi.

Parameters:
- task_id: The Hermes Kanban task ID (from pi_delegate response)

Returns the task status and any results/artifacts.
"""

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The Kanban task ID",
                },
            },
            "required": ["task_id"],
        }

    def execute(self, task_id: str, **kwargs) -> str:
        """
        Get task result from Kanban.

        Args:
            task_id: Kanban task ID

        Returns:
            JSON string with task result
        """
        try:
            from ..kanban import get_task_result

            result = get_task_result(
                db_path=self.config.kanban_db,
                task_id=task_id,
            )

            if result:
                return json.dumps({
                    "ok": True,
                    "task_id": task_id,
                    **result,
                })
            else:
                return json.dumps({
                    "ok": False,
                    "error": f"Task {task_id} not found",
                })

        except Exception as e:
            logger.error(f"pi result error: {e}")
            return json.dumps({
                "ok": False,
                "error": str(e),
            })
