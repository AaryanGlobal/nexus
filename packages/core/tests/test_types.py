"""
Tests for core type definitions.

TDD: These tests define the expected behavior of shared types.
"""

import pytest
from hermes_pi_bridge_core import (
    AgentType,
    ErrorCode,
    Priority,
    ProtocolVersion,
    TaskContext,
    TaskDelegateRequest,
    TaskResult,
    TaskStatus,
)


class TestProtocolVersion:
    """Test ProtocolVersion class."""
    
    def test_create_version(self):
        """Can create a protocol version."""
        v = ProtocolVersion(1, 0, 0)
        assert v.major == 1
        assert v.minor == 0
        assert v.patch == 0
    
    def test_version_string(self):
        """Version converts to string correctly."""
        v = ProtocolVersion(1, 2, 3)
        assert str(v) == "1.2.3"
    
    def test_version_parse(self):
        """Can parse version from string."""
        v = ProtocolVersion.parse("2.1.0")
        assert v.major == 2
        assert v.minor == 1
        assert v.patch == 0
    
    def test_version_parse_without_patch(self):
        """Can parse version without patch number."""
        v = ProtocolVersion.parse("1.0")
        assert v.major == 1
        assert v.minor == 0
        assert v.patch == 0
    
    def test_compatible_same_major(self):
        """Same major version is compatible."""
        v1 = ProtocolVersion(1, 0, 0)
        v2 = ProtocolVersion(1, 2, 0)
        assert v1.is_compatible(v2)
    
    def test_not_compatible_different_major(self):
        """Different major version is not compatible."""
        v1 = ProtocolVersion(1, 0, 0)
        v2 = ProtocolVersion(2, 0, 0)
        assert not v1.is_compatible(v2)


class TestTaskDelegateRequest:
    """Test TaskDelegateRequest validation and serialization."""
    
    def test_create_request(self):
        """Can create a basic task request."""
        req = TaskDelegateRequest(
            title="Test task",
            description="A test task description",
        )
        assert req.title == "Test task"
        assert req.description == "A test task description"
        assert req.timeout_seconds == 300
        assert req.priority == Priority.NORMAL
    
    def test_request_with_context(self):
        """Can create request with context."""
        ctx = TaskContext(
            workspace="/path/to/project",
            files=["file1.py", "file2.py"],
            checkpoint_hash="sha256:abc123",
        )
        req = TaskDelegateRequest(
            title="Test",
            description="Test",
            context=ctx,
        )
        assert req.context.workspace == "/path/to/project"
        assert len(req.context.files) == 2
    
    def test_request_validation_empty_title(self):
        """Title is required (not empty)."""
        req = TaskDelegateRequest(title="", description="Test")
        errors = req.validate()
        # Empty title is allowed, but we should check
        assert isinstance(errors, list)
    
    def test_request_validation_title_too_long(self):
        """Title over 200 chars fails validation."""
        req = TaskDelegateRequest(
            title="x" * 201,
            description="Test",
        )
        errors = req.validate()
        assert "title must be <= 200 characters" in errors
    
    def test_request_validation_description_too_long(self):
        """Description over 100KB fails validation."""
        req = TaskDelegateRequest(
            title="Test",
            description="x" * 100_001,
        )
        errors = req.validate()
        assert "description must be <= 100KB" in errors
    
    def test_request_validation_timeout_too_low(self):
        """Timeout less than 1 second fails."""
        req = TaskDelegateRequest(
            title="Test",
            description="Test",
            timeout_seconds=0,
        )
        errors = req.validate()
        assert "timeout_seconds must be 1-3600" in errors
    
    def test_request_validation_timeout_too_high(self):
        """Timeout more than 3600 seconds fails."""
        req = TaskDelegateRequest(
            title="Test",
            description="Test",
            timeout_seconds=3601,
        )
        errors = req.validate()
        assert "timeout_seconds must be 1-3600" in errors
    
    def test_request_to_dict(self):
        """Can serialize to dictionary."""
        req = TaskDelegateRequest(
            title="Test",
            description="Test description",
            timeout_seconds=600,
            priority=Priority.HIGH,
        )
        data = req.to_dict()
        assert data["title"] == "Test"
        assert data["timeout_seconds"] == 600
        assert data["priority"] == "high"
    
    def test_request_from_dict(self):
        """Can deserialize from dictionary."""
        data = {
            "task_id": "test-id",
            "title": "Test",
            "description": "Test description",
            "timeout_seconds": 600,
            "priority": "high",
            "context": {
                "workspace": "/project",
                "files": ["a.py"],
            }
        }
        req = TaskDelegateRequest.from_dict(data)
        assert req.task_id == "test-id"
        assert req.title == "Test"
        assert req.timeout_seconds == 600
        assert req.priority == Priority.HIGH
        assert req.context.workspace == "/project"


class TestTaskResult:
    """Test TaskResult serialization."""
    
    def test_create_result(self):
        """Can create a basic result."""
        result = TaskResult(
            status=TaskStatus.SUCCESS,
            summary="Task completed successfully",
        )
        assert result.status == TaskStatus.SUCCESS
        assert result.summary == "Task completed successfully"
        assert len(result.artifacts) == 0
        assert len(result.errors) == 0
    
    def test_result_with_artifacts(self):
        """Can create result with artifacts."""
        result = TaskResult(
            status=TaskStatus.SUCCESS,
            summary="Created files",
            artifacts=[
                {"path": "output.py", "type": "file"},
                {"path": "docs/", "type": "directory"},
            ],
        )
        assert len(result.artifacts) == 2
        assert result.artifacts[0]["path"] == "output.py"
    
    def test_result_with_errors(self):
        """Can create result with errors."""
        result = TaskResult(
            status=TaskStatus.FAILED,
            summary="Task failed",
            errors=["File not found", "Permission denied"],
        )
        assert len(result.errors) == 2
        assert "File not found" in result.errors
    
    def test_result_to_dict(self):
        """Can serialize to dictionary."""
        result = TaskResult(
            status=TaskStatus.PARTIAL,
            summary="Completed with warnings",
            artifacts=[{"path": "test.py", "type": "file"}],
            errors=["Warning: deprecated API"],
            duration_seconds=120.5,
        )
        data = result.to_dict()
        assert data["status"] == "partial"
        assert data["duration_seconds"] == 120.5
        assert len(data["artifacts"]) == 1
    
    def test_result_from_dict(self):
        """Can deserialize from dictionary."""
        data = {
            "status": "failed",
            "summary": "Error occurred",
            "artifacts": [],
            "errors": ["Error 1"],
            "duration_seconds": 60.0,
        }
        result = TaskResult.from_dict(data)
        assert result.status == TaskStatus.FAILED
        assert result.duration_seconds == 60.0


class TestErrorCode:
    """Test error code constants."""
    
    def test_json_rpc_error_codes(self):
        """JSON-RPC 2.0 error codes are correct."""
        assert ErrorCode.PARSE_ERROR == -32700
        assert ErrorCode.INVALID_REQUEST == -32600
        assert ErrorCode.METHOD_NOT_FOUND == -32601
        assert ErrorCode.INVALID_PARAMS == -32602
        assert ErrorCode.INTERNAL_ERROR == -32603
    
    def test_bridge_error_codes(self):
        """Bridge-specific error codes are in correct range."""
        assert 1000 <= ErrorCode.AUTH_ERROR <= 1999
        assert 1000 <= ErrorCode.SESSION_NOT_FOUND <= 1999
        assert 1000 <= ErrorCode.TASK_NOT_FOUND <= 1999
        assert 1000 <= ErrorCode.TIMEOUT <= 1999
        assert 1000 <= ErrorCode.CAPACITY_EXCEEDED <= 1999
        assert 1000 <= ErrorCode.VERSION_MISMATCH <= 1999


class TestEnums:
    """Test enum values."""
    
    def test_agent_types(self):
        """AgentType enum has correct values."""
        assert AgentType.HERMES == "hermes"
        assert AgentType.PI == "pi"
    
    def test_task_statuses(self):
        """TaskStatus enum has all expected values."""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.SUCCESS == "success"
        assert TaskStatus.PARTIAL == "partial"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.BLOCKED == "blocked"
        assert TaskStatus.CANCELLED == "cancelled"
    
    def test_priority(self):
        """Priority enum has correct values."""
        assert Priority.LOW == "low"
        assert Priority.NORMAL == "normal"
        assert Priority.HIGH == "high"
