"""
HTTP transport client for pi communication.
"""

import logging
from typing import Any

import httpx
from hermes_pi_bridge_core import TaskDelegateRequest

logger = logging.getLogger(__name__)


class PiHttpClient:
    """
    HTTP client for communicating with pi bridge HTTP server.

    The pi extension runs an HTTP server that exposes the bridge API.
    This client makes requests to that server.
    """

    def __init__(
        self,
        base_url: str,
        auth_token: str = "",
        timeout: float = 30.0,
    ):
        """
        Initialize HTTP client.

        Args:
            base_url: Base URL of pi bridge server
            auth_token: Optional authentication token
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout

        self._client: httpx.AsyncClient | None = None

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
    ) -> dict[str, Any]:
        """
        Make HTTP request to pi server.

        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request body

        Returns:
            Response data
        """
        url = f"{self.base_url}/api/v1/{endpoint.lstrip('/')}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    json=data,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
                return {"success": False, "error": f"HTTP {e.response.status_code}"}
            except Exception as e:
                logger.error(f"Request error: {e}")
                return {"success": False, "error": str(e)}

    def get_status(self) -> dict[str, Any]:
        """
        Check pi agent status.

        Returns:
            Status information
        """
        import asyncio
        return asyncio.run(self._request("POST", "/agent.status", {
            "agent_type": "pi",
            "version": "1.0.0",
        }))

    def delegate_task(
        self,
        task: TaskDelegateRequest,
    ) -> dict[str, Any]:
        """
        Delegate a task to pi.

        Args:
            task: Task delegate request

        Returns:
            Delegation result with task_id
        """
        import asyncio
        return asyncio.run(self._request("POST", "/task.delegate", {
            "task_id": task.task_id,
            "title": task.title,
            "description": task.description,
            "context": task.context.to_dict() if task.context else None,
            "timeout_seconds": task.timeout_seconds,
            "priority": task.priority.value,
        }))

    def report_result(
        self,
        task_id: str,
        status: str,
        summary: str,
        artifacts: list | None = None,
        errors: list | None = None,
    ) -> dict[str, Any]:
        """
        Report task result to pi.

        Args:
            task_id: Task ID
            status: Result status (success/failed/blocked)
            summary: Result summary
            artifacts: Created files
            errors: Error messages

        Returns:
            Acknowledgment
        """
        import asyncio
        return asyncio.run(self._request("POST", "/task.result", {
            "task_id": task_id,
            "status": status,
            "summary": summary,
            "artifacts": artifacts or [],
            "errors": errors or [],
        }))
