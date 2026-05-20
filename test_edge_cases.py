"""TDD: Edge cases and failure modes"""
import pytest
import time
from hermes_pi_bridge_core.autonomous import AutonomousNHIL, AutonomousConfig


class TestEdgeCases:
    """Test edge cases and failure modes."""
    
    def test_rapid_pause_resume(self):
        """Rapid pause/resume shouldn't break the agent."""
        agent = AutonomousNHIL()
        agent.start()
        
        for _ in range(10):
            agent.pause()
            agent.resume()
        
        assert agent.running is True
        agent.stop()
    
    def test_inject_task_while_paused(self):
        """Injecting task while paused."""
        agent = AutonomousNHIL()
        agent.start()
        agent.pause()
        
        result = agent.inject_task("Test task")
        assert result is not None
        
        agent.stop()
    
    def test_stop_while_processing(self):
        """Stop while tasks are being processed."""
        agent = AutonomousNHIL()
        agent.start()
        
        # Inject several tasks
        for i in range(5):
            agent.inject_task(f"Task {i}")
        
        # Stop immediately
        agent.stop()
        assert agent.running is False
    
    def test_multiple_agents(self):
        """Multiple agents coexisting."""
        agents = [AutonomousNHIL() for _ in range(3)]
        
        for a in agents:
            a.start()
        
        assert all(a.running for a in agents)
        
        for a in agents:
            a.stop()
    
    def test_config_with_invalid_values(self):
        """Config with edge case values."""
        config = AutonomousConfig(
            scan_interval_seconds=-1,  # Invalid
            max_execution_duration_seconds=0,  # Edge case
        )
        agent = AutonomousNHIL(config=config)
        
        # Should still work (or handle gracefully)
        assert agent.config.scan_interval_seconds >= 0
        agent.start()
        agent.stop()
    
    def test_concurrent_task_injection(self):
        """Concurrent task injection."""
        import threading
        
        agent = AutonomousNHIL()
        agent.start()
        
        results = []
        def inject():
            for i in range(5):
                r = agent.inject_task(f"Task {i}")
                results.append(r)
        
        threads = [threading.Thread(target=inject) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(results) == 15
        agent.stop()
    
    def test_audit_log_overflow(self):
        """Audit log doesn't grow indefinitely."""
        agent = AutonomousNHIL()
        
        # Add many entries
        for i in range(200):
            agent._audit_log.append(type('AuditEntry', (), {
                'timestamp': time.time(),
                'action': 'test',
                'details': f'Test {i}',
                'user': 'test'
            })())
        
        # Should be bounded
        log = agent.get_audit_log(limit=100)
        assert len(log) <= 100
    
    def test_executor_timeout(self):
        """Executor timeout handling."""
        agent = AutonomousNHIL()
        
        result = agent.execute_command("sleep 30")  # Would timeout
        assert result is not None
        assert 'success' in result
    
    def test_scanner_nonexistent_path(self):
        """Scanner with nonexistent paths."""
        config = AutonomousConfig(scan_paths=["/nonexistent/path/12345"])
        agent = AutonomousNHIL(config=config)
        
        tasks = agent.scanner.scan(force=True)
        assert isinstance(tasks, list)
    
    def test_evolution_on_empty_failure(self):
        """Evolution triggered with empty error."""
        agent = AutonomousNHIL()
        agent.start()
        
        # Trigger evolution manually
        result = agent.evolution.attempt_fix("test task", "")
        assert result is not None
        
        agent.stop()


class TestFailureModes:
    """Test failure mode handling."""
    
    def test_invalid_task_description(self):
        """Handle invalid task descriptions."""
        agent = AutonomousNHIL()
        
        result = agent.inject_task("")
        assert result is not None
    
    def test_unicode_task(self):
        """Handle unicode in tasks."""
        agent = AutonomousNHIL()
        
        result = agent.inject_task("Task with émojis 🚀 and unicode 你好")
        assert result is not None
    
    def test_very_long_task(self):
        """Handle very long task descriptions."""
        agent = AutonomousNHIL()
        
        long_task = "A" * 10000
        result = agent.inject_task(long_task)
        assert result is not None
    
    def test_special_characters_in_command(self):
        """Handle special characters in commands."""
        agent = AutonomousNHIL()
        
        result = agent.execute_command("echo 'test with $HOME and backticks`ls`quotes'")
        assert result['success'] is True
