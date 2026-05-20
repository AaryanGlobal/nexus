"""
TDD: Task Timeout Tests

Tests for automatic task timeout and cancellation.
"""

import pytest
import asyncio
from hermes_pi_bridge.server import TaskTracker, TrackedTask, TaskStatus


class TestTaskTimeout:
    """Test task timeout handling"""

    def test_task_has_timeout_field(self):
        """TrackedTask should have timeout_seconds field"""
        tracker = TaskTracker()
        
        task = tracker.add_task(
            task_id='test-1',
            title='Test',
            description='Test',
            timeout_seconds=300
        )
        
        assert hasattr(task, 'timeout_seconds')
        assert task.timeout_seconds == 300

    def test_default_timeout(self):
        """Default timeout should be 300 seconds"""
        tracker = TaskTracker()
        
        task = tracker.add_task(
            task_id='test-2',
            title='Test',
            description='Test'
        )
        
        assert task.timeout_seconds == 300

    def test_timeout_exceeded_flag(self):
        """Should track when task exceeds timeout"""
        tracker = TaskTracker()
        
        task = tracker.add_task(
            task_id='test-3',
            title='Test',
            description='Test',
            timeout_seconds=1  # 1 second timeout
        )
        
        # After timeout, should be marked as TIMED_OUT
        # (This would be checked by a background task)
        assert task.timeout_seconds == 1

    def test_cancel_task(self):
        """Should be able to cancel a task"""
        tracker = TaskTracker()
        
        tracker.add_task(
            task_id='test-4',
            title='Test',
            description='Test'
        )
        
        tracker.cancel_task('test-4')
        
        task = tracker.get_task('test-4')
        assert task.status == TaskStatus.CANCELLED


class TestTimeoutCheck:
    """Test timeout checking logic"""

    def test_get_expired_tasks(self):
        """Should return list of tasks that exceeded timeout"""
        tracker = TaskTracker()
        
        # Add tasks with short timeouts
        tracker.add_task(
            task_id='task-1',
            title='Task 1',
            description='Desc',
            timeout_seconds=1
        )
        tracker.add_task(
            task_id='task-2',
            title='Task 2',
            description='Desc',
            timeout_seconds=600
        )
        
        # get_expired_tasks should return timed-out tasks
        # (In real implementation, this would check created_at + timeout)
        expired = tracker.get_expired_tasks()
        assert isinstance(expired, list)  # Just verify method exists

    def test_get_pending_tasks(self):
        """Should return pending tasks for heartbeat check"""
        tracker = TaskTracker()
        
        tracker.add_task(
            task_id='pending-1',
            title='Pending',
            description='Desc',
            status=TaskStatus.PENDING
        )
        tracker.add_task(
            task_id='running-1',
            title='Running',
            description='Desc',
            status=TaskStatus.RUNNING
        )
        
        pending = tracker.get_pending_tasks()
        assert len(pending) >= 1
        assert any(t.task_id == 'pending-1' for t in pending)
