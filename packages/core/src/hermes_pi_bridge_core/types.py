"""
Shared type definitions for Hermes-Pi Bridge.

These types are used by both Hermes (Python) and pi (TypeScript) sides.
Keeping them synchronized ensures protocol compatibility.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AgentType(StrEnum):
    """Type of agent."""
    HERMES = "hermes"
    PI = "pi"


class TaskStatus(StrEnum):
    """Status of a delegated task."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class Priority(StrEnum):
    """Task priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass(frozen=True)
class ProtocolVersion:
    """Semantic version for protocol compatibility."""
    major: int
    minor: int
    patch: int = 0

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def is_compatible(self, other: ProtocolVersion) -> bool:
        """Check if versions are compatible (same major)."""
        return self.major == other.major

    @classmethod
    def parse(cls, version: str) -> ProtocolVersion:
        """Parse version string like '1.0.0'."""
        parts = version.split(".")
        return cls(
            major=int(parts[0]),
            minor=int(parts[1]),
            patch=int(parts[2]) if len(parts) > 2 else 0
        )


@dataclass
class AgentStatus:
    """Status response from agent."""
    agent_type: AgentType
    version: str
    available: bool
    capabilities: list[str]
    max_concurrent: int
    uptime_seconds: float = 0.0


@dataclass
class TaskContext:
    """Context for a delegated task."""
    workspace: str
    files: list[str] = field(default_factory=list)
    checkpoint_hash: str | None = None
    environment: dict[str, str] = field(default_factory=dict)


@dataclass
class TaskDelegateRequest:
    """Request to delegate a task."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    context: TaskContext | None = None
    timeout_seconds: int = 300
    priority: Priority = Priority.NORMAL

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "timeout_seconds": self.timeout_seconds,
            "priority": self.priority.value,
        }
        if self.context:
            result["context"] = {
                "workspace": self.context.workspace,
                "files": self.context.files,
                "checkpoint_hash": self.context.checkpoint_hash,
                "environment": self.context.environment,
            }
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskDelegateRequest:
        """Create from dictionary."""
        context = None
        if "context" in data and data["context"]:
            ctx_data = data["context"]
            context = TaskContext(
                workspace=ctx_data.get("workspace", ""),
                files=ctx_data.get("files", []),
                checkpoint_hash=ctx_data.get("checkpoint_hash"),
                environment=ctx_data.get("environment", {}),
            )
        return cls(
            task_id=data.get("task_id", str(uuid.uuid4())),
            title=data.get("title", ""),
            description=data.get("description", ""),
            context=context,
            timeout_seconds=data.get("timeout_seconds", 300),
            priority=Priority(data.get("priority", "normal")),
        )

    def validate(self) -> list[str]:
        """Validate request, return list of errors."""
        errors = []
        if not self.task_id:
            errors.append("task_id is required")
        if len(self.title) > 200:
            errors.append("title must be <= 200 characters")
        if len(self.description) > 100_000:
            errors.append("description must be <= 100KB")
        if self.timeout_seconds < 1 or self.timeout_seconds > 3600:
            errors.append("timeout_seconds must be 1-3600")
        return errors


@dataclass
class TaskResult:
    """Result of a completed task."""
    status: TaskStatus
    summary: str
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    checkpoint_hash: str | None = None
    duration_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "summary": self.summary,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "checkpoint_hash": self.checkpoint_hash,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskResult:
        """Create from dictionary."""
        return cls(
            status=TaskStatus(data.get("status", "failed")),
            summary=data.get("summary", ""),
            artifacts=data.get("artifacts", []),
            errors=data.get("errors", []),
            checkpoint_hash=data.get("checkpoint_hash"),
            duration_seconds=data.get("duration_seconds"),
        )


# Error code constants
class ErrorCode:
    """Standard error codes per JSON-RPC 2.0 and bridge extension."""
    # JSON-RPC 2.0 reserved codes
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # Bridge-specific codes (1000-1999)
    AUTH_ERROR = 1000
    SESSION_NOT_FOUND = 1001
    TASK_NOT_FOUND = 1002
    TIMEOUT = 1003
    CAPACITY_EXCEEDED = 1004
    VERSION_MISMATCH = 1005
    CONTEXT_CONFLICT = 1006
