"""TDD: Integration tests - everything works together"""
import pytest
import sys

sys.path.insert(0, 'packages/core/src')
sys.path.insert(0, 'packages/hermes-plugin/src')


class TestIntegration:
    """Test that all packages integrate correctly."""
    
    def test_core_imports_work(self):
        """Core module imports correctly."""
        from hermes_pi_bridge_core.autonomous import AutonomousNHIL
        from hermes_pi_bridge_core.executor import SafeExecutor
        from hermes_pi_bridge_core.scanner import WorkScanner
        assert AutonomousNHIL is not None
        assert SafeExecutor is not None
        assert WorkScanner is not None
    
    def test_hermes_plugin_imports_work(self):
        """Hermes plugin imports correctly."""
        from hermes_pi_bridge.tools.delegate import PiDelegateTool
        from hermes_pi_bridge.tools.result import PiResultTool
        from hermes_pi_bridge.tools.status import PiStatusTool
        assert PiDelegateTool is not None
        assert PiResultTool is not None
        assert PiStatusTool is not None
    
    def test_hermes_config_imports_work(self):
        """Hermes config imports correctly."""
        from hermes_pi_bridge.config import BridgeConfig
        from hermes_pi_bridge.kanban import create_task, update_task_status
        assert BridgeConfig is not None
        assert create_task is not None
        assert update_task_status is not None
    
    def test_agent_can_use_hermes_tools(self):
        """Agent can interact with Hermes tools."""
        from hermes_pi_bridge_core.autonomous import AutonomousNHIL
        from hermes_pi_bridge.kanban import create_task
        import tempfile
        
        agent = AutonomousNHIL()
        
        # Create a task in temp database
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/kanban.db"
            task_id = create_task(db_path, title="test", description="test")
            assert task_id is not None
        
        assert agent is not None
    
    def test_full_workflow(self):
        """Complete workflow: discover → analyze → execute → learn."""
        from hermes_pi_bridge_core.autonomous import AutonomousNHIL
        
        agent = AutonomousNHIL()
        agent.start()
        
        # Execute task
        result = agent.execute_command("echo 'integration test'")
        assert result['success'] is True
        
        # Learn from task
        agent.inject_task("debug test task")
        
        # Verify learning
        stats = agent.learner.get_learned_stats()
        assert 'total_patterns' in stats
        
        agent.stop()
    
    def test_security_integration(self):
        """Security works across all components."""
        from hermes_pi_bridge_core.autonomous import AutonomousNHIL
        
        agent = AutonomousNHIL()
        
        # Blocked commands
        assert not agent.execute_command("rm -rf /")['success']
        assert not agent.execute_command("sudo shutdown")['success']
        
        # Safe commands
        assert agent.execute_command("echo safe")['success']
    
    def test_persistence_integration(self):
        """Persistence works across agent restarts."""
        import tempfile
        from hermes_pi_bridge_core.autonomous import AutonomousNHIL, AutonomousConfig
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config = AutonomousConfig(storage_path=f"{tmpdir}/state.json")
            
            # First session
            agent1 = AutonomousNHIL(config=config)
            agent1.start()
            agent1.inject_task("persist test")
            agent1.stop()
            
            # Second session
            agent2 = AutonomousNHIL(config=config)
            assert agent2.previous_state is not None
            agent2.stop()
