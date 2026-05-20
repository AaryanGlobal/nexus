"""TDD: Control interface tests"""
import pytest
from hermes_pi_bridge_core.autonomous import AutonomousNHIL


class TestAgentControl:
    """Test agent control methods."""
    
    def test_pause_resume(self):
        agent = AutonomousNHIL()
        agent.start()
        
        # Pause
        agent.pause()
        assert agent.is_paused is True
        
        # Resume
        agent.resume()
        assert agent.is_paused is False
        
        agent.stop()
    
    def test_manual_task_injection(self):
        agent = AutonomousNHIL()
        agent.start()
        
        # Inject task
        result = agent.inject_task("Test task", priority="high")
        assert result is not None
        
        agent.stop()
    
    def test_override_task(self):
        agent = AutonomousNHIL()
        agent.start()
        
        # Force override
        result = agent.override_decision("run locally", "Test override")
        assert result is not None
        
        agent.stop()
    
    def test_get_status(self):
        agent = AutonomousNHIL()
        status = agent.get_status()
        assert "running" in status
        assert "tasks_completed" in status
    
    def test_stop_while_paused(self):
        agent = AutonomousNHIL()
        agent.start()
        agent.pause()
        agent.stop()
        assert agent.running is False
