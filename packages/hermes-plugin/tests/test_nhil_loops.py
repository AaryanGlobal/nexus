"""
NHIL Autonomous Loop Tests - Python side
"""
import pytest
from hermes_pi_bridge.server import TaskTracker, TrackedTask, TaskStatus


class TestSelfCorrection:
    """Test self-correcting behavior"""

    def test_retry_on_failure(self):
        """Should track failures for retry"""
        tracker = TaskTracker(max_consecutive_failures=3)
        
        task = tracker.add_task(
            task_id='test-1',
            title='Test Task',
            description='A test'
        )
        
        # Fail twice
        tracker.update_result('test-1', TaskStatus.FAILED)
        tracker.update_result('test-1', TaskStatus.FAILED)
        
        # Should still be tracked
        tracked = tracker.get_task('test-1')
        assert tracked is not None
        assert tracked.consecutive_failures == 2
        
    def test_reset_on_success(self):
        """Should reset failure count on success"""
        tracker = TaskTracker()
        
        task = tracker.add_task(
            task_id='test-1',
            title='Test Task',
            description='A test'
        )
        
        tracker.update_result('test-1', TaskStatus.FAILED)
        tracker.update_result('test-1', TaskStatus.FAILED)
        
        # Success resets
        tracker.update_result('test-1', TaskStatus.SUCCESS)
        
        tracked = tracker.get_task('test-1')
        assert tracked.consecutive_failures == 0

    def test_no_retry_after_limit(self):
        """Should not retry after max failures"""
        tracker = TaskTracker(max_consecutive_failures=3)
        
        task = tracker.add_task(
            task_id='test-1',
            title='Test Task',
            description='A test'
        )
        
        # Fail 3 times (at limit)
        for _ in range(3):
            tracker.update_result('test-1', TaskStatus.FAILED)
        
        # At limit - should_retry is False (failures >= max)
        assert not tracker.should_retry('test-1')


class TestTaskLifecycle:
    """Test task lifecycle"""

    def test_pending_to_running(self):
        """Task starts as pending"""
        tracker = TaskTracker()
        task = tracker.add_task('test-1', 'Test', 'Desc')
        assert task.status == TaskStatus.PENDING

    def test_all_status_values(self):
        """All status values exist"""
        statuses = list(TaskStatus)
        assert TaskStatus.PENDING in statuses
        assert TaskStatus.RUNNING in statuses
        assert TaskStatus.SUCCESS in statuses
        assert TaskStatus.FAILED in statuses
        assert TaskStatus.PARTIAL in statuses
        assert TaskStatus.BLOCKED in statuses
        assert TaskStatus.CANCELLED in statuses


class TestKanbanMapping:
    """Test kanban ID tracking"""

    def test_kanban_id_mapping(self):
        """Should track kanban <-> task mapping"""
        tracker = TaskTracker()
        
        tracker.add_task(
            task_id='task-1',
            title='Test',
            kanban_id='kanban-abc'
        )
        
        # Method is get_by_kanban_id, returns TrackedTask
        task = tracker.get_by_kanban_id('kanban-abc')
        assert task is not None
        assert task.task_id == 'task-1'
