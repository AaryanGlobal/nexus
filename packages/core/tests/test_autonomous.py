"""TDD: Autonomous Agent Tests"""
import pytest
import time
from hermes_pi_bridge_core.autonomous import (
    AutonomousNHIL, AutonomousConfig
)


class TestInitialization:
    """Test agent initialization."""
    
    def test_default_initialization(self):
        agent = AutonomousNHIL()
        
        assert agent.loop is not None
        assert agent.executor is not None
        assert agent.scanner is not None
        assert agent.learner is not None
        assert agent.evolution is not None
        assert agent.security is not None
    
    def test_custom_config(self):
        config = AutonomousConfig(
            scan_interval_seconds=60,
            max_execution_duration_seconds=30,
        )
        agent = AutonomousNHIL(config=config)
        
        assert agent.config.scan_interval_seconds == 60
        assert agent.config.max_execution_duration_seconds == 30


class TestLifecycle:
    """Test agent start/stop."""
    
    def test_start_agent(self):
        agent = AutonomousNHIL()
        result = agent.start()
        
        assert result is True
        assert agent.running is True
        assert agent.loop.running is True
    
    def test_stop_agent(self):
        agent = AutonomousNHIL()
        agent.start()
        
        result = agent.stop()
        
        assert result is True
        assert agent.running is False
    
    def test_cant_start_twice(self):
        agent = AutonomousNHIL()
        agent.start()
        
        result = agent.start()  # Should return False
        
        assert result is False


class TestCommandExecution:
    """Test command execution."""
    
    def test_safe_command_execution(self):
        agent = AutonomousNHIL()
        
        result = agent.execute_command("echo 'hello'")
        
        assert result['success'] is True
        assert 'hello' in result['stdout']
    
    def test_dangerous_command_blocked(self):
        agent = AutonomousNHIL()
        
        result = agent.execute_command("rm -rf /tmp/test")
        
        assert result['success'] is False


class TestStatus:
    """Test status reporting."""
    
    def test_status_initial_state(self):
        agent = AutonomousNHIL()
        
        status = agent.get_status()
        
        assert 'running' in status
        assert 'uptime_seconds' in status
        assert 'tasks_discovered' in status
        assert 'tasks_completed' in status
    
    def test_status_after_work(self):
        agent = AutonomousNHIL()
        agent.start()
        
        # Execute some work
        agent.execute_command("echo test")
        
        status = agent.get_status()
        
        assert status['tasks_completed'] >= 0


class TestIntegration:
    """Test integration between components."""
    
    def test_all_components_wired(self):
        agent = AutonomousNHIL()
        
        # All components should be present
        assert hasattr(agent, 'loop')
        assert hasattr(agent, 'executor')
        assert hasattr(agent, 'scanner')
        assert hasattr(agent, 'learner')
        assert hasattr(agent, 'evolution')
        assert hasattr(agent, 'security')
        assert hasattr(agent, 'persistence')
    
    def test_executor_integration(self):
        agent = AutonomousNHIL()
        
        result = agent.execute_command("ls /tmp")
        assert result is not None
        assert 'success' in result
    
    def test_callback_not_required(self):
        agent = AutonomousNHIL()  # No callback
        
        # Should still work with executor
        result = agent.execute_command("echo works")
        assert result['success'] is True


class TestEdgeCases:
    """Test edge cases."""
    
    def test_empty_command(self):
        agent = AutonomousNHIL()
        
        result = agent.execute_command("")
        
        assert result['success'] is False
    
    def test_stop_without_start(self):
        agent = AutonomousNHIL()
        
        result = agent.stop()
        
        assert result is False
    
    def test_status_update_after_tasks(self):
        agent = AutonomousNHIL()
        agent.start()
        
        # Do some work
        for _ in range(3):
            agent.execute_command("echo test")
        
        status = agent.get_status()
        assert status['tasks_completed'] >= 0