"""
Hermes-Pi Bridge Core
====================

Shared types and protocol definitions for Hermes-Pi Bridge.
This package is used by both Hermes plugin and standalone tools.
"""

from .types import (
    AgentStatus,
    AgentType,
    ErrorCode,
    Priority,
    ProtocolVersion,
    TaskContext,
    TaskDelegateRequest,
    TaskResult,
    TaskStatus,
)

__version__ = "1.0.0"
__all__ = [
    "AgentType",
    "AgentStatus",
    "ErrorCode",
    "Priority",
    "ProtocolVersion",
    "TaskContext",
    "TaskDelegateRequest",
    "TaskResult",
    "TaskStatus",
]
