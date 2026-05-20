"""
Hermes Bridge HTTP Server.

This server runs alongside Hermes and receives task results from pi.
It updates the Hermes Kanban and notifies the agent of completed tasks.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# =============================================================================
# Pydantic Models
# =============================================================================

class TaskStatus(StrEnum):
    """Task status values."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskResultRequest(BaseModel):
    """Request to report task result."""
    task_id: str
    status: TaskStatus
    summary: str = ""
    artifacts: list[dict[str, Any]] = []
    errors: list[str] = []
    checkpoint_hash: str | None = None
    duration_seconds: float | None = None


class TaskDelegateRequest(BaseModel):
    """Request to delegate a task."""
    task_id: str
    title: str
    description: str = ""
    context: dict[str, Any] | None = None
    timeout_seconds: int = 300
    priority: str = "normal"


class TaskCancelRequest(BaseModel):
    """Request to cancel a task."""
    task_id: str
    reason: str = ""


class AgentStatusRequest(BaseModel):
    """Request for agent status."""
    agent_type: str = "hermes"
    version: str = "1.0.0"


# =============================================================================
# Error Codes
# =============================================================================

class ErrorCode:
    """JSON-RPC 2.0 + bridge error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    AUTH_ERROR = 1000
    SESSION_NOT_FOUND = 1001
    TASK_NOT_FOUND = 1002
    TIMEOUT = 1003
    CAPACITY_EXCEEDED = 1004
    VERSION_MISMATCH = 1005


# =============================================================================
# Task Tracking
# =============================================================================

@dataclass
class TrackedTask:
    """A task being tracked by the bridge."""
    task_id: str
    kanban_id: str | None = None
    pi_task_id: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    title: str = ""
    description: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: dict[str, Any] | None = None
    consecutive_failures: int = 0
    error: str | None = None
    timeout_seconds: int = 300  # Default 5 minute timeout
    is_expired: bool = False


class TaskTracker:
    """Tracks delegated tasks and their status."""

    def __init__(self, max_consecutive_failures: int = 3):
        self.tasks: dict[str, TrackedTask] = {}
        self.kanban_to_pi: dict[str, str] = {}  # kanban_id -> pi_task_id
        self.pi_to_kanban: dict[str, str] = {}  # pi_task_id -> kanban_id
        self.max_consecutive_failures = max_consecutive_failures

    def add_task(
        self,
        task_id: str,
        title: str,
        description: str = "",
        kanban_id: str | None = None,
        timeout_seconds: int = 300,
        status: TaskStatus = TaskStatus.PENDING,
    ) -> TrackedTask:
        """Add a new task to track."""
        task = TrackedTask(
            task_id=task_id,
            kanban_id=kanban_id,
            title=title,
            description=description,
            timeout_seconds=timeout_seconds,
            status=status,
        )
        self.tasks[task_id] = task
        if kanban_id:
            self.kanban_to_pi[kanban_id] = task_id
        return task

    def get_task(self, task_id: str) -> TrackedTask | None:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def get_by_kanban_id(self, kanban_id: str) -> TrackedTask | None:
        """Get task by kanban ID."""
        pi_task_id = self.kanban_to_pi.get(kanban_id)
        if pi_task_id:
            return self.tasks.get(pi_task_id)
        return None

    def update_result(
        self,
        task_id: str,
        status: TaskStatus,
        summary: str = "",
        artifacts: list[dict[str, Any]] = None,
        errors: list[str] = None,
    ) -> TrackedTask | None:
        """Update task with result from pi."""
        task = self.tasks.get(task_id)
        if not task:
            return None

        task.status = status
        task.completed_at = time.time()
        task.result = {
            "status": status.value if isinstance(status, TaskStatus) else status,
            "summary": summary,
            "artifacts": artifacts or [],
            "errors": errors or [],
        }

        if status == TaskStatus.FAILED:
            task.consecutive_failures += 1
            task.error = "; ".join(errors) if errors else "Unknown error"
        else:
            task.consecutive_failures = 0
            task.error = None

        # Update kanban if linked
        if task.kanban_id:
            self._update_kanban(task)

        return task

    def cancel_task(self, task_id: str, reason: str = "") -> TrackedTask | None:
        """Cancel a task."""
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = time.time()
        task.error = reason or "Cancelled by request"
        
        if task.kanban_id:
            self._update_kanban(task)
        
        return task

    def mark_expired(self, task_id: str) -> TrackedTask | None:
        """Mark a task as timed out."""
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        task.status = TaskStatus.FAILED
        task.is_expired = True
        task.completed_at = time.time()
        task.error = "Task exceeded timeout"
        
        if task.kanban_id:
            self._update_kanban(task)
        
        return task

    def get_expired_tasks(self) -> list[TrackedTask]:
        """Get all tasks that have exceeded their timeout."""
        current_time = time.time()
        expired = []
        
        for task in self.tasks.values():
            if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                elapsed = current_time - task.created_at
                if elapsed > task.timeout_seconds:
                    expired.append(task)
        
        return expired

    def get_pending_tasks(self) -> list[TrackedTask]:
        """Get all pending tasks for heartbeat checks."""
        return [
            task for task in self.tasks.values()
            if task.status == TaskStatus.PENDING
        ]

    def should_retry(self, task_id: str) -> bool:
        """Check if task should be retried (circuit breaker)."""
        task = self.tasks.get(task_id)
        if not task:
            return False
        return task.consecutive_failures < self.max_consecutive_failures

    def get_stats(self) -> dict[str, Any]:
        """Get tracking statistics."""
        return {
            "total_tasks": len(self.tasks),
            "by_status": {
                status.value: sum(
                    1 for t in self.tasks.values()
                    if t.status == status
                )
                for status in TaskStatus
            },
        }

    def _update_kanban(self, task: TrackedTask) -> None:
        """Update Hermes Kanban with task result."""
        # This will be implemented with actual Kanban integration
        logger.info(
            f"Updating kanban {task.kanban_id} with status {task.status.value}"
        )


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(title="Hermes-Pi Bridge Server")
task_tracker = TaskTracker()


# =============================================================================
# Middleware
# =============================================================================

@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    """Add CORS headers to all responses."""
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


# =============================================================================
# Health Check
# =============================================================================

@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "tasks": task_tracker.get_stats(),
    }


# =============================================================================
# Agent Status
# =============================================================================

@app.post("/api/v1/agent.status")
async def agent_status(
    request: Request,
    body: dict[str, Any],
    authorization: str | None = Header(None),
):
    """Check Hermes agent status."""
    # Version check
    client_version = body.get("version", "0.0.0")
    client_major = int(client_version.split(".")[0])
    server_major = 1

    if client_major != server_major:
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": ErrorCode.VERSION_MISMATCH,
                    "message": "Version mismatch",
                    "data": {
                        "client_version": client_version,
                        "server_version": "1.0.0",
                    },
                },
                "id": body.get("id"),
            },
        )

    return {
        "jsonrpc": "2.0",
        "result": {
            "available": True,
            "version": "1.0.0",
            "capabilities": ["delegate", "status", "result"],
            "max_concurrent": 2,
            "uptime_seconds": time.time(),
        },
        "id": body.get("id"),
    }


# =============================================================================
# Task Result (pi reports results here)
# =============================================================================

@app.post("/api/v1/task.result")
async def task_result(
    request: Request,
    body: dict[str, Any],
    authorization: str | None = Header(None),
):
    """
    Receive task result from pi.

    This is called by pi when a delegated task completes.
    """
    task_id = body.get("task_id")
    if not task_id:
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": ErrorCode.INVALID_PARAMS,
                    "message": "Missing task_id",
                },
                "id": body.get("id"),
            },
        )

    task = task_tracker.get_task(task_id)
    if not task:
        # Try looking up by kanban ID
        task = task_tracker.get_by_kanban_id(task_id)

    if not task:
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": ErrorCode.TASK_NOT_FOUND,
                    "message": f"Task {task_id} not found",
                },
                "id": body.get("id"),
            },
        )

    # Update task with result
    status_str = body.get("status", "failed")
    try:
        status = TaskStatus(status_str)
    except ValueError:
        status = TaskStatus.FAILED

    updated_task = task_tracker.update_result(
        task_id=task.task_id,
        status=status,
        summary=body.get("summary", ""),
        artifacts=body.get("artifacts", []),
        errors=body.get("errors", []),
    )

    # Emit event for Hermes agent to pick up
    await emit_task_completed(updated_task)

    return {
        "jsonrpc": "2.0",
        "result": {
            "acknowledged": True,
            "task_id": task.task_id,
            "kanban_id": task.kanban_id,
            "should_retry": task_tracker.should_retry(task.task_id),
        },
        "id": body.get("id"),
    }


# =============================================================================
# Task Status
# =============================================================================

@app.post("/api/v1/task.status")
async def task_status(
    request: Request,
    body: dict[str, Any],
    authorization: str | None = Header(None),
):
    """Get status of a task."""
    task_id = body.get("task_id")
    if not task_id:
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": ErrorCode.INVALID_PARAMS,
                    "message": "Missing task_id",
                },
                "id": body.get("id"),
            },
        )

    task = task_tracker.get_task(task_id)
    if not task:
        task = task_tracker.get_by_kanban_id(task_id)

    if not task:
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": ErrorCode.TASK_NOT_FOUND,
                    "message": f"Task {task_id} not found",
                },
                "id": body.get("id"),
            },
        )

    progress = _calculate_progress(task)

    return {
        "jsonrpc": "2.0",
        "result": {
            "task_id": task.task_id,
            "kanban_id": task.kanban_id,
            "status": task.status.value,
            "progress_percent": progress,
            "title": task.title,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "error": task.error,
            "consecutive_failures": task.consecutive_failures,
        },
        "id": body.get("id"),
    }


# =============================================================================
# Task Cancel
# =============================================================================

@app.post("/api/v1/task.cancel")
async def task_cancel(
    request: Request,
    body: dict[str, Any],
    authorization: str | None = Header(None),
):
    """Cancel a task."""
    task_id = body.get("task_id")
    if not task_id:
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": ErrorCode.INVALID_PARAMS,
                    "message": "Missing task_id",
                },
                "id": body.get("id"),
            },
        )

    task = task_tracker.get_task(task_id)
    if not task:
        return JSONResponse(
            status_code=200,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": ErrorCode.TASK_NOT_FOUND,
                    "message": f"Task {task_id} not found",
                },
                "id": body.get("id"),
            },
        )

    task.status = TaskStatus.CANCELLED
    task.completed_at = time.time()

    return {
        "jsonrpc": "2.0",
        "result": {
            "cancelled": True,
            "task_id": task.task_id,
        },
        "id": body.get("id"),
    }


# =============================================================================
# Agent Ready (pi announces readiness)
# =============================================================================

@app.post("/api/v1/agent.ready")
async def agent_ready(
    request: Request,
    body: dict[str, Any],
    authorization: str | None = Header(None),
):
    """pi announces it's ready to receive tasks."""
    logger.info(f"pi agent ready: {body}")

    return {
        "jsonrpc": "2.0",
        "result": {
            "acknowledged": True,
        },
        "id": body.get("id"),
    }


# =============================================================================
# Task Delegate (for testing / internal use)
# =============================================================================

@app.post("/api/v1/task.delegate")
async def task_delegate(
    request: Request,
    body: dict[str, Any],
    authorization: str | None = Header(None),
):
    """Internal: Delegate a task (usually Hermes calls pi instead)."""
    return JSONResponse(
        status_code=200,
        content={
            "jsonrpc": "2.0",
            "error": {
                "code": ErrorCode.METHOD_NOT_FOUND,
                "message": "Use pi HTTP server to delegate tasks to pi",
            },
            "id": body.get("id"),
        },
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _calculate_progress(task: TrackedTask) -> int:
    """Calculate task progress percentage."""
    if task.status == TaskStatus.PENDING:
        return 0
    elif task.status == TaskStatus.RUNNING:
        if not task.started_at:
            return 0
        elapsed = time.time() - task.started_at
        # Assume 5 minute average task
        return min(90, int((elapsed / 300) * 100))
    elif task.status in (TaskStatus.SUCCESS, TaskStatus.PARTIAL):
        return 100
    else:  # FAILED, BLOCKED, CANCELLED
        return 100


async def emit_task_completed(task: TrackedTask) -> None:
    """
    Emit event when task completes.

    This should trigger Hermes to pick up the result.
    """
    logger.info(
        f"Task completed: {task.task_id} -> {task.status.value} "
        f"(summary: {task.result.get('summary', '')[:50] if task.result else ''})"
    )
    # The Hermes agent should be notified via hooks/callbacks
    # For now, just log


# =============================================================================
# Server Entry Point
# =============================================================================

def run_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    reload: bool = False,
) -> None:
    """Run the bridge server."""
    import uvicorn

    uvicorn.run(
        "hermes_pi_bridge.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    run_server()
