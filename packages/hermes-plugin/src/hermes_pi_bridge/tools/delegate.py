"""
pi_delegate tool - Delegate tasks to pi agent.
"""

import json
import logging
from typing import Any

from hermes_pi_bridge_core import Priority, TaskContext, TaskDelegateRequest

from ..config import BridgeConfig
from ..kanban import create_task, update_task_status
from ..transport import PiHttpClient

logger = logging.getLogger(__name__)


def tool_ok(data: Any) -> str:
    """Format successful tool result."""
    return json.dumps({"ok": True, **data})


def tool_error(message: str) -> str:
    """Format error tool result."""
    return json.dumps({"ok": False, "error": message})


class PiDelegateTool:
    """
    Tool to delegate tasks to pi agent.

    Usage in Hermes:
        /pi_delegate task="Analyze this codebase" context="..." timeout=300
    """

    def __init__(self, config: BridgeConfig):
        self.config = config
        self.client = PiHttpClient(
            base_url=config.pi_url,
            auth_token=config.auth_token,
        )

    @property
    def name(self) -> str:
        return "pi_delegate"

    @property
    def description(self) -> str:
        return """Delegate a task to pi agent.

pi is better suited for:
- Long-running research tasks
- Code review and refactoring
- Documentation writing
- Testing and QA tasks

The task is tracked via Hermes Kanban for visibility.

Required parameters:
- task: The task description (string)

Optional parameters:
- context: Additional context or files (string)
- workspace: Working directory (string, default: current)
- timeout: Timeout in seconds (integer, default: 300)
- priority: Task priority (low/normal/high, default: normal)
"""

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task description for pi",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context (code, files, instructions)",
                },
                "workspace": {
                    "type": "string",
                    "description": "Working directory for pi",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 300)",
                    "default": 300,
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high"],
                    "description": "Task priority",
                    "default": "normal",
                },
            },
            "required": ["task"],
        }

    def execute(
        self,
        task: str,
        context: str | None = None,
        workspace: str | None = None,
        timeout: int | None = None,
        priority: str = "normal",
        **kwargs,
    ) -> str:
        """
        Execute the pi delegation.

        Args:
            task: Task description
            context: Additional context
            workspace: Working directory
            timeout: Timeout in seconds
            priority: Task priority

        Returns:
            JSON string with delegation result
        """
        timeout = timeout or self.config.timeout_seconds
        priority_enum = Priority(priority)

        # Create task request
        task_request = TaskDelegateRequest(
            title=task[:50] + "..." if len(task) > 50 else task,
            description=task,
            context=TaskContext(
                workspace=workspace or "",
                files=[],
            ) if workspace else None,
            timeout_seconds=timeout,
            priority=priority_enum,
        )

        # Validate request
        errors = task_request.validate()
        if errors:
            return tool_error(f"Invalid request: {', '.join(errors)}")

        try:
            # Create Kanban task for tracking
            kanban_id = create_task(
                db_path=self.config.kanban_db,
                title=f"[pi] {task[:80]}",
                description=json.dumps({
                    "task": task,
                    "context": context,
                    "workspace": workspace,
                    "task_request": task_request.to_dict(),
                }),
                max_runtime_seconds=timeout,
            )

            # Send to pi via HTTP
            result = self.client.delegate_task(task_request)

            if result.get("success"):
                update_task_status(
                    db_path=self.config.kanban_db,
                    task_id=kanban_id,
                    status="running",
                    notes=f"Delegated to pi: {result.get('pi_task_id')}",
                )

                return tool_ok({
                    "kanban_id": kanban_id,
                    "pi_task_id": result.get("task_id"),
                    "status": "delegated",
                    "timeout": timeout,
                })
            else:
                update_task_status(
                    db_path=self.config.kanban_db,
                    task_id=kanban_id,
                    status="failed",
                    notes=f"Delegation failed: {result.get('error')}",
                )
                return tool_error(f"pi delegation failed: {result.get('error')}")

        except Exception as e:
            logger.error(f"pi delegation error: {e}")
            return tool_error(f"Failed to delegate to pi: {e}")
