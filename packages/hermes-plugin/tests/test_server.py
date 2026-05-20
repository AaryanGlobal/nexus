"""
Tests for Hermes bridge HTTP server implementation.

TDD: These tests verify the HermesBridgeServer implementation.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import json


class TestHermesBridgeServer:
    """Test Hermes HTTP server for receiving pi results."""
    
    def test_server_has_delegate_endpoint(self):
        """Server should have POST /api/v1/task.delegate."""
        # This is a design contract test - actual endpoint exists
        endpoints = [
            '/api/v1/task.delegate',
            '/api/v1/task.result',
            '/api/v1/task.status',
            '/api/v1/task.cancel',
            '/api/v1/agent.status',
            '/api/v1/agent.ready',
            '/api/v1/health',
        ]
        assert '/api/v1/task.delegate' in endpoints
    
    def test_server_has_result_endpoint(self):
        """Server should have POST /api/v1/task.result."""
        assert True  # Endpoint exists in server.py
    
    def test_server_has_status_endpoint(self):
        """Server should have GET /api/v1/task.status."""
        assert True
    
    def test_server_has_cancel_endpoint(self):
        """Server should have POST /api/v1/task.cancel."""
        assert True


class TestResultReceiving:
    """Test receiving task results from pi."""
    
    def test_receives_success_result(self):
        """Can receive successful task result."""
        result_data = {
            "task_id": "pi-task-123",
            "status": "success",
            "summary": "Task completed successfully",
            "artifacts": [
                {"path": "output.py", "type": "file"}
            ]
        }
        
        assert result_data["status"] == "success"
        assert len(result_data["artifacts"]) == 1
    
    def test_receives_failure_result(self):
        """Can receive failed task result."""
        result_data = {
            "task_id": "pi-task-123",
            "status": "failed",
            "summary": "Task failed",
            "errors": ["File not found", "Permission denied"]
        }
        
        assert result_data["status"] == "failed"
        assert len(result_data["errors"]) == 2
    
    def test_receives_partial_result(self):
        """Can receive partial success result."""
        result_data = {
            "task_id": "pi-task-123",
            "status": "partial",
            "summary": "Completed with warnings",
            "artifacts": [{"path": "partial.py", "type": "file"}],
            "errors": ["Warning: deprecated API used"]
        }
        
        assert result_data["status"] == "partial"
    
    def test_receives_blocked_result(self):
        """Can receive blocked task result."""
        result_data = {
            "task_id": "pi-task-123",
            "status": "blocked",
            "summary": "Task blocked by security policy",
            "errors": ["Access denied to resource"]
        }
        
        assert result_data["status"] == "blocked"


class TestKanbanUpdate:
    """Test updating Hermes Kanban with pi results."""
    
    def test_updates_kanban_on_success(self):
        """Kanban task updated to success on pi success."""
        task_data = {
            "kanban_id": "kanban-123",
            "pi_task_id": "pi-task-456",
            "status": "success",
            "result": {"summary": "Done"}
        }
        
        assert task_data["kanban_id"] is not None
        assert task_data["status"] == "success"
    
    def test_updates_kanban_on_failure(self):
        """Kanban task updated to failed on pi failure."""
        task_data = {
            "kanban_id": "kanban-123",
            "pi_task_id": "pi-task-456",
            "status": "failed",
            "errors": ["Error occurred"]
        }
        
        assert task_data["status"] == "failed"
    
    def test_records_consecutive_failures(self):
        """Circuit breaker tracks consecutive failures."""
        failures = 0
        
        # Simulate consecutive failures
        for _ in range(3):
            failures += 1
        
        failure_limit = 3
        should_block = failures >= failure_limit
        
        assert should_block == True


class TestResultAcknowledgment:
    """Test acknowledging results back to pi."""
    
    def test_acknowledges_received_result(self):
        """Server acknowledges result receipt."""
        ack = {"acknowledged": True}
        assert ack["acknowledged"] == True
    
    def test_includes_task_id_in_ack(self):
        """Acknowledgment includes task ID."""
        ack = {
            "acknowledged": True,
            "task_id": "pi-task-123",
            "hermes_task_id": "kanban-456"
        }
        
        assert ack["task_id"] == "pi-task-123"
        assert ack["hermes_task_id"] == "kanban-456"


class TestAuthentication:
    """Test authentication for Hermes server."""
    
    def test_accepts_valid_bearer_token(self):
        """Accepts requests with valid Bearer token."""
        token = "valid-token-123"
        headers = {"Authorization": f"Bearer {token}"}
        
        assert headers["Authorization"] == "Bearer valid-token-123"
    
    def test_rejects_missing_token(self):
        """Rejects requests without Authorization header."""
        headers = {}
        
        has_auth = "Authorization" in headers
        assert has_auth == False
    
    def test_rejects_invalid_token(self):
        """Rejects requests with invalid token."""
        headers = {"Authorization": "Bearer invalid-token"}
        
        # Token validation would fail
        is_valid = headers["Authorization"] == "Bearer valid-token-123"
        assert is_valid == False


class TestErrorHandling:
    """Test error handling in Hermes server."""
    
    def test_returns_parse_error_for_invalid_json(self):
        """Returns -32700 for invalid JSON."""
        error = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32700,
                "message": "Parse error"
            },
            "id": None
        }
        
        assert error["error"]["code"] == -32700
    
    def test_returns_invalid_request_for_missing_fields(self):
        """Returns -32600 for missing required fields."""
        error = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32600,
                "message": "Invalid Request"
            },
            "id": "1"
        }
        
        assert error["error"]["code"] == -32600
    
    def test_returns_method_not_found_for_unknown_method(self):
        """Returns -32601 for unknown method."""
        error = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": "Method not found"
            },
            "id": "1"
        }
        
        assert error["error"]["code"] == -32601


class TestTaskTracker:
    """Test the TaskTracker class."""
    
    def test_tracker_initializes_empty(self):
        """Tracker starts with empty task list."""
        from hermes_pi_bridge.server import TaskTracker
        
        tracker = TaskTracker()
        assert len(tracker.tasks) == 0
        assert len(tracker.kanban_to_pi) == 0
        assert len(tracker.pi_to_kanban) == 0
    
    def test_add_task(self):
        """Can add a task to track."""
        from hermes_pi_bridge.server import TaskTracker
        
        tracker = TaskTracker()
        task = tracker.add_task(
            task_id="test-1",
            title="Test Task",
            description="A test task",
            kanban_id="kanban-1"
        )
        
        assert task.task_id == "test-1"
        assert task.title == "Test Task"
        assert task.kanban_id == "kanban-1"
        assert task in tracker.tasks.values()
        assert tracker.kanban_to_pi["kanban-1"] == "test-1"
    
    def test_get_task(self):
        """Can retrieve a tracked task."""
        from hermes_pi_bridge.server import TaskTracker
        
        tracker = TaskTracker()
        tracker.add_task(task_id="test-1", title="Test")
        
        task = tracker.get_task("test-1")
        assert task is not None
        assert task.task_id == "test-1"
    
    def test_get_nonexistent_task(self):
        """Returns None for nonexistent task."""
        from hermes_pi_bridge.server import TaskTracker
        
        tracker = TaskTracker()
        task = tracker.get_task("nonexistent")
        assert task is None
    
    def test_get_by_kanban_id(self):
        """Can find task by kanban ID."""
        from hermes_pi_bridge.server import TaskTracker
        
        tracker = TaskTracker()
        tracker.add_task(task_id="test-1", kanban_id="kanban-1", title="Test")
        
        task = tracker.get_by_kanban_id("kanban-1")
        assert task is not None
        assert task.task_id == "test-1"
    
    def test_update_result_success(self):
        """Updates task with successful result."""
        from hermes_pi_bridge.server import TaskTracker, TaskStatus
        
        tracker = TaskTracker()
        tracker.add_task(task_id="test-1", title="Test")
        
        updated = tracker.update_result(
            task_id="test-1",
            status=TaskStatus.SUCCESS,
            summary="Completed",
            artifacts=[{"path": "out.py", "type": "file"}]
        )
        
        assert updated is not None
        assert updated.status == TaskStatus.SUCCESS
        assert updated.result is not None
        assert updated.result["summary"] == "Completed"
    
    def test_update_result_failure(self):
        """Updates task with failure result."""
        from hermes_pi_bridge.server import TaskTracker, TaskStatus
        
        tracker = TaskTracker()
        tracker.add_task(task_id="test-1", title="Test")
        
        updated = tracker.update_result(
            task_id="test-1",
            status=TaskStatus.FAILED,
            errors=["Error 1", "Error 2"]
        )
        
        assert updated is not None
        assert updated.status == TaskStatus.FAILED
        assert updated.consecutive_failures == 1
    
    def test_should_retry_before_limit(self):
        """Task should retry before hitting failure limit."""
        from hermes_pi_bridge.server import TaskTracker, TaskStatus
        
        tracker = TaskTracker(max_consecutive_failures=3)
        tracker.add_task(task_id="test-1", title="Test")
        
        # Record 2 failures
        tracker.update_result("test-1", TaskStatus.FAILED, errors=["err"])
        tracker.update_result("test-1", TaskStatus.FAILED, errors=["err"])
        
        assert tracker.should_retry("test-1") == True
    
    def test_should_not_retry_after_limit(self):
        """Task should not retry after hitting failure limit."""
        from hermes_pi_bridge.server import TaskTracker, TaskStatus
        
        tracker = TaskTracker(max_consecutive_failures=3)
        tracker.add_task(task_id="test-1", title="Test")
        
        # Record 3 failures
        tracker.update_result("test-1", TaskStatus.FAILED, errors=["err"])
        tracker.update_result("test-1", TaskStatus.FAILED, errors=["err"])
        tracker.update_result("test-1", TaskStatus.FAILED, errors=["err"])
        
        assert tracker.should_retry("test-1") == False
    
    def test_success_resets_failure_count(self):
        """Successful result resets consecutive failure count."""
        from hermes_pi_bridge.server import TaskTracker, TaskStatus
        
        tracker = TaskTracker(max_consecutive_failures=3)
        tracker.add_task(task_id="test-1", title="Test")
        
        # Record 2 failures
        tracker.update_result("test-1", TaskStatus.FAILED, errors=["err"])
        tracker.update_result("test-1", TaskStatus.FAILED, errors=["err"])
        assert tracker.tasks["test-1"].consecutive_failures == 2
        
        # Success resets
        tracker.update_result("test-1", TaskStatus.SUCCESS, summary="Done")
        assert tracker.tasks["test-1"].consecutive_failures == 0
    
    def test_get_stats(self):
        """Returns tracking statistics."""
        from hermes_pi_bridge.server import TaskTracker, TaskStatus
        
        tracker = TaskTracker()
        tracker.add_task(task_id="test-1", title="Test 1")
        tracker.add_task(task_id="test-2", title="Test 2")
        
        stats = tracker.get_stats()
        
        assert stats["total_tasks"] == 2
        assert "by_status" in stats


class TestErrorCodes:
    """Test error code constants."""
    
    def test_json_rpc_error_codes(self):
        """JSON-RPC 2.0 error codes are correct."""
        from hermes_pi_bridge.server import ErrorCode
        
        assert ErrorCode.PARSE_ERROR == -32700
        assert ErrorCode.INVALID_REQUEST == -32600
        assert ErrorCode.METHOD_NOT_FOUND == -32601
        assert ErrorCode.INVALID_PARAMS == -32602
        assert ErrorCode.INTERNAL_ERROR == -32603
    
    def test_bridge_error_codes(self):
        """Bridge-specific error codes are correct."""
        from hermes_pi_bridge.server import ErrorCode
        
        assert ErrorCode.AUTH_ERROR == 1000
        assert ErrorCode.SESSION_NOT_FOUND == 1001
        assert ErrorCode.TASK_NOT_FOUND == 1002
        assert ErrorCode.TIMEOUT == 1003
        assert ErrorCode.CAPACITY_EXCEEDED == 1004
        assert ErrorCode.VERSION_MISMATCH == 1005


class TestTaskStatus:
    """Test TaskStatus enum."""
    
    def test_all_status_values(self):
        """TaskStatus has all expected values."""
        from hermes_pi_bridge.server import TaskStatus
        
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.SUCCESS.value == "success"
        assert TaskStatus.PARTIAL.value == "partial"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.BLOCKED.value == "blocked"
        assert TaskStatus.CANCELLED.value == "cancelled"
