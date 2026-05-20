"""TDD: Audit and monitoring tests"""
import pytest
from hermes_pi_bridge_core.autonomous import AutonomousNHIL


class TestCurrentActivity:
    """Test seeing what agent is doing."""
    
    def test_get_current_activity(self):
        agent = AutonomousNHIL()
        agent.start()
        
        activity = agent.get_current_activity()
        assert 'state' in activity
        assert 'pending_tasks' in activity
        assert 'loop_state' in activity
        
        agent.stop()
    
    def test_activity_when_idle(self):
        agent = AutonomousNHIL()
        activity = agent.get_current_activity()
        assert activity['state'] == 'idle'


class TestTaskApproval:
    """Test approve/reject discovered tasks."""
    
    def test_approve_task(self):
        agent = AutonomousNHIL()
        agent.start()
        
        result = agent.approve_task("Test task")
        assert result is not None
        
        agent.stop()
    
    def test_reject_task(self):
        agent = AutonomousNHIL()
        agent.start()
        
        result = agent.reject_task("Test task", reason="Not needed")
        assert result is not None
        
        agent.stop()


class TestAuditLog:
    """Test audit logging."""
    
    def test_audit_log_exists(self):
        agent = AutonomousNHIL()
        
        log = agent.get_audit_log()
        assert log is not None
        assert isinstance(log, list)
    
    def test_audit_log_records_action(self):
        agent = AutonomousNHIL()
        agent.start()
        
        agent.inject_task("Test task")
        
        log = agent.get_audit_log()
        assert len(log) >= 1


class TestAgentQuery:
    """Test querying the agent."""
    
    def test_ask_question(self):
        agent = AutonomousNHIL()
        
        response = agent.ask("What are you doing?")
        assert response is not None
        assert isinstance(response, str)
    
    def test_ask_status(self):
        agent = AutonomousNHIL()
        agent.start()
        
        response = agent.ask("What is your status?")
        assert 'running' in response.lower() or 'completed' in response.lower()
        
        agent.stop()