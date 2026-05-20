"""
TDD: Kanban Integration Tests

These tests define the expected behavior for Hermes Kanban integration.
"""

import pytest
from hermes_pi_bridge.server import TaskTracker, TrackedTask, TaskStatus


class TestKanbanIntegration:
    """Test that results are properly synced to Hermes Kanban"""

    def test_update_kanban_called_on_result(self):
        """When task completes, kanban should be updated"""
        tracker = TaskTracker()
        
        task = tracker.add_task(
            task_id='test-1',
            title='Test Task',
            description='A test',
            kanban_id='kanban-abc'
        )
        
        # Complete the task
        tracker.update_result('test-1', TaskStatus.SUCCESS)
        
        # Kanban task should exist
        kanban_task = tracker.get_by_kanban_id('kanban-abc')
        assert kanban_task is not None
        assert kanban_task.task_id == 'test-1'
        assert kanban_task.status == TaskStatus.SUCCESS

    def test_kanban_updated_on_failure(self):
        """Failed tasks should update kanban with FAILED status"""
        tracker = TaskTracker()
        
        tracker.add_task(
            task_id='test-2',
            title='Failing Task',
            description='Will fail',
            kanban_id='kanban-def'
        )
        
        tracker.update_result('test-2', TaskStatus.FAILED)
        
        kanban_task = tracker.get_by_kanban_id('kanban-def')
        assert kanban_task.status == TaskStatus.FAILED

    def test_kanban_id_not_required(self):
        """Tasks without kanban_id should still work"""
        tracker = TaskTracker()
        
        task = tracker.add_task(
            task_id='test-3',
            title='No Kanban',
            description='No kanban link'
        )
        
        assert task.kanban_id is None
        tracker.update_result('test-3', TaskStatus.SUCCESS)
        # Should not raise


class TestKanbanTaskMapping:
    """Test mapping between pi task_id and kanban_id"""

    def test_bidirectional_lookup(self):
        """Should be able to find task by both IDs"""
        tracker = TaskTracker()
        
        tracker.add_task(
            task_id='pi-task-123',
            title='Test',
            description='Test',
            kanban_id='hermes-kanban-456'
        )
        
        # Find by kanban_id
        by_kanban = tracker.get_by_kanban_id('hermes-kanban-456')
        assert by_kanban is not None
        assert by_kanban.task_id == 'pi-task-123'
        
        # Find by task_id
        by_task = tracker.get_task('pi-task-123')
        assert by_task is not None
        assert by_task.kanban_id == 'hermes-kanban-456'

    def test_multiple_kanban_ids(self):
        """Should handle multiple tasks per kanban"""
        tracker = TaskTracker()
        
        tracker.add_task(
            task_id='task-a',
            title='Task A',
            description='A',
            kanban_id='shared-kanban'
        )
        tracker.add_task(
            task_id='task-b',
            title='Task B',
            description='B',
            kanban_id='shared-kanban'
        )
        
        # Both should be accessible
        assert tracker.get_task('task-a') is not None
        assert tracker.get_task('task-b') is not None
        assert tracker.get_by_kanban_id('shared-kanban').task_id in ['task-a', 'task-b']
