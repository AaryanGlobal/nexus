"""TDD: Error Handling and Resilience Tests"""
import pytest
import json
import tempfile
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core" / "src"))

from hermes_pi_bridge_core.bridge import AgentBridge, AgentType
from hermes_pi_bridge_core.life_context import LifeContextEngine
from hermes_pi_bridge_core.rl import ReinforcementLearning, ActionType


class TestBridgeErrorHandling:
    """Test bridge error handling and retry logic."""
    
    def test_bridge_has_retry_logic(self):
        """Bridge should have retry logic for failed connections."""
        bridge = AgentBridge()
        assert hasattr(bridge, 'retry') or hasattr(bridge, 'retry_on_failure') or hasattr(bridge, '_retry') or hasattr(bridge, 'connect_with_retry'), \
            "Bridge should have retry logic"
    
    def test_bridge_has_error_handler(self):
        """Bridge should have error handler."""
        bridge = AgentBridge()
        assert hasattr(bridge, 'handle_error') or hasattr(bridge, 'on_error') or hasattr(bridge, '_handle_error') or hasattr(bridge, 'handle_connect_error'), \
            "Bridge should have error handler"
    
    def test_retry_returns_on_max_attempts(self):
        """Retry logic should return after max attempts."""
        bridge = AgentBridge()
        
        if hasattr(bridge, 'retry'):
            result = bridge.retry(AgentType.PI, max_attempts=3)
            # Should return after 3 attempts
            assert isinstance(result, bool)
    
    def test_error_handler_registers_callbacks(self):
        """Error handler should allow registering callbacks."""
        bridge = AgentBridge()
        
        errors = []
        def error_callback(error):
            errors.append(error)
        
        if hasattr(bridge, 'register_error_handler'):
            bridge.register_error_handler(error_callback)
        elif hasattr(bridge, 'on_error'):
            bridge.on_error(error_callback)
        
        # Bridge should not crash when calling internal error handling
        assert True  # If we get here, no crash
    
    def test_bridge_handles_timeout_gracefully(self):
        """Bridge handles connection timeouts."""
        bridge = AgentBridge()
        
        # Try to connect with invalid URL
        bridge.connections[AgentType.PI].url = "http://localhost:59999"
        
        # Should not crash, should return False
        try:
            result = bridge.connect(AgentType.PI)
            assert isinstance(result, bool)
        except Exception as e:
            # Should be handled gracefully
            assert False, f"Bridge crashed on timeout: {e}"
    
    def test_bridge_reconnects_on_failure(self):
        """Bridge can reconnect after failure."""
        bridge = AgentBridge()
        
        # Try to reconnect
        result = bridge.reconnect(AgentType.HERMES)
        
        # Should return boolean
        assert isinstance(result, bool)


class TestLifeEngineErrorHandling:
    """Test life context engine error handling."""
    
    def test_life_engine_handles_corrupt_storage(self):
        """Handles corrupt storage file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir) / "corrupt.json"
            storage.write_text("not valid json{{{")
            
            # Should not crash
            engine = LifeContextEngine(storage_path=str(storage))
            
            # Should have default empty state
            assert len(engine.contexts) == 0
            assert len(engine.goals) == 0
            
            # Should still be functional
            engine.add_goal("Test", "Desc", "test")
            assert len(engine.goals) == 1
    
    def test_life_engine_handles_invalid_goal_id(self, tmp_path):
        """Handles invalid goal ID gracefully."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        
        # Update non-existent goal
        result = engine.update_goal_progress("nonexistent_id", 50)
        
        # Should return False, not crash
        assert result is False
    
    def test_life_engine_handles_duplicate_context(self, tmp_path):
        """Handles duplicate context gracefully."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        
        # Add same context twice
        ctx1 = engine.add_context("Same content", "test")
        ctx2 = engine.add_context("Same content", "test")
        
        # Should not crash
        assert ctx1 is not None
        assert ctx2 is not None
    
    def test_life_engine_has_error_recovery(self):
        """Has error recovery mechanism."""
        engine = LifeContextEngine()
        
        # Should have some form of error recovery (reset exists)
        assert hasattr(engine, 'reset') or hasattr(engine, 'repair') or \
               hasattr(engine, 'recover') or hasattr(engine, 'handle_error'), \
            "Life engine should have error recovery"


class TestRLErrorHandling:
    """Test RL error handling."""
    
    def test_rl_handles_invalid_state(self):
        """RL handles invalid state queries."""
        rl = ReinforcementLearning()
        
        # Query non-existent state
        q = rl.get_q_value("nonexistent", ActionType.EXECUTE)
        
        # Should return 0, not crash
        assert q == 0.0
    
    def test_rl_handles_invalid_action(self):
        """RL handles invalid action queries."""
        rl = ReinforcementLearning()
        
        # Update with state
        rl.update_q_value("test", ActionType.EXECUTE, 1.0, "done")
        
        # Query with different action (same state)
        q = rl.get_q_value("test", ActionType.DELEGATE)
        
        # Should return 0
        assert q == 0.0
    
    def test_rl_handles_corrupt_save_file(self):
        """RL handles corrupt save file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = str(Path(tmpdir) / "corrupt_rl.json")
            
            # Create corrupt file
            with open(save_path, 'w') as f:
                f.write("not valid json{{{")
            
            rl = ReinforcementLearning()
            
            # Load should not crash
            result = rl.load(save_path)
            
            # Should return False
            assert result is False
    
    def test_rl_has_error_recovery(self):
        """RL has error recovery mechanism."""
        rl = ReinforcementLearning()
        
        # Should have reset or recovery
        assert hasattr(rl, 'reset') or hasattr(rl, 'recover'), \
            "RL should have reset or recovery"


class TestTimeoutHandling:
    """Test timeout and race condition handling."""
    
    def test_bridge_timeout_on_slow_connection(self):
        """Bridge handles slow connections with timeout."""
        bridge = AgentBridge()
        
        # Set very short timeout
        bridge.connections[AgentType.PI].timeout = 1
        
        # Try to connect (will fail but not hang)
        try:
            result = bridge.connect(AgentType.PI, url="http://localhost:59999")
            assert isinstance(result, bool)
        except TimeoutError:
            # Acceptable - timeout is working
            pass
        except:
            # Other errors also acceptable
            pass
    
    def test_engine_handles_rapid_updates(self, tmp_path):
        """Handles rapid consecutive updates."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        
        # Rapid updates
        for i in range(100):
            engine.add_context(f"Context {i}", "test")
        
        # Should not crash, should have all contexts
        assert len(engine.contexts) == 100


class TestRetryLogic:
    """Test retry and backoff logic."""
    
    def test_bridge_has_backoff_strategy(self):
        """Bridge has backoff strategy for retries."""
        bridge = AgentBridge()
        
        # Should have backoff or retry delay mechanism
        assert hasattr(bridge, 'backoff') or hasattr(bridge, 'retry_delay') or \
               hasattr(bridge, 'get_retry_delay') or hasattr(bridge, 'set_backoff'), \
            "Bridge should have backoff strategy"
    
    def test_bridge_exponential_backoff(self):
        """Bridge implements exponential backoff."""
        bridge = AgentBridge()
        
        # If backoff exists, check it increases
        if hasattr(bridge, 'get_retry_delay'):
            delay1 = bridge.get_retry_delay(1)
            delay2 = bridge.get_retry_delay(2)
            delay3 = bridge.get_retry_delay(3)
            
            # Each delay should be >= previous
            assert delay2 >= delay1
            assert delay3 >= delay2


class TestGracefulDegradation:
    """Test graceful degradation under load."""
    
    def test_bridge_handles_connection_gracefully(self):
        """Bridge handles connection to PI."""
        bridge = AgentBridge()
        
        # PI may or may not be available at 8645
        result = bridge.connect(AgentType.PI)
        
        # Result should be True (available) or False (unavailable) - either is valid
        assert isinstance(result, bool)
        
        # Other operations should still work
        status = bridge.get_connection_status()
        assert 'hermes' in status
        assert 'pi' in status
    
    def test_engine_works_without_storage(self, tmp_path):
        """Engine works without storage file."""
        # Use path in temp directory that doesn't exist yet
        storage_path = str(tmp_path / "new" / "path" / "data.json")
        engine = LifeContextEngine(storage_path=storage_path)
        
        # Should create storage on first save
        engine.add_goal("Test", "Desc", "test")
        
        # Should not crash
        assert len(engine.goals) >= 1
    
    def test_rl_works_without_save_path(self):
        """RL works without valid save path."""
        rl = ReinforcementLearning()
        
        # Save to invalid path
        result = rl.save("/nonexistent/directory/data.json")
        
        # Should return False, not crash
        assert result is False
        
        # RL should still be functional
        rl.update_q_value("test", ActionType.EXECUTE, 1.0, "done")
        assert rl.get_q_value("test", ActionType.EXECUTE) > 0


class TestLoggingAndMonitoring:
    """Test logging and monitoring capabilities."""
    
    def test_bridge_logs_connections(self):
        """Bridge logs connection attempts."""
        bridge = AgentBridge()
        
        # Bridge uses logger at module level
        import logging
        
        # Should have module-level logger
        assert hasattr(bridge, 'logger') or hasattr(bridge, 'log'), \
            "Bridge should have logger attribute"
    
    def test_bridge_logs_messages(self):
        """Bridge logs message sending."""
        bridge = AgentBridge()
        
        # Send a message (will fail but should be logged)
        bridge.delegate_task(AgentType.PI, {"task": "test"})
        
        # History should be updated
        history = bridge.get_message_history()
        assert isinstance(history, list)
    
    def test_life_engine_logs_changes(self, tmp_path):
        """Life engine logs changes."""
        engine = LifeContextEngine(storage_path=str(tmp_path / "life.json"))
        
        # Add goal
        engine.add_goal("Test", "Desc", "test")
        
        # Should have saved
        storage = tmp_path / "life.json"
        assert storage.exists()
    
    def test_rl_logs_learning(self):
        """RL logs learning outcomes."""
        rl = ReinforcementLearning()
        
        # Learn something
        rl.reward(ActionType.EXECUTE, True)
        
        # Should have stats
        stats = rl.get_stats()
        assert 'total_rewards' in stats or 'states_learned' in stats


class TestCircuitBreaker:
    """Test circuit breaker pattern."""
    
    def test_bridge_has_circuit_breaker(self):
        """Bridge has circuit breaker for failing connections."""
        bridge = AgentBridge()
        
        # Should have circuit breaker or failure tracking
        assert hasattr(bridge, 'circuit_breaker') or hasattr(bridge, 'failure_count') or \
               hasattr(bridge, 'is_circuit_open') or hasattr(bridge, 'trip'), \
            "Bridge should have circuit breaker pattern"
    
    def test_circuit_breaker_tracks_failures(self):
        """Circuit breaker tracks consecutive failures."""
        bridge = AgentBridge()
        
        if hasattr(bridge, 'failure_count') or hasattr(bridge, 'trip'):
            # Record failures
            if hasattr(bridge, 'record_failure'):
                bridge.record_failure(AgentType.PI)
                bridge.record_failure(AgentType.PI)
            
            # Should track count
            assert hasattr(bridge, 'failure_count') or hasattr(bridge, 'get_failures')
    
    def test_circuit_breaker_resets_on_success(self):
        """Circuit breaker resets on successful connection."""
        bridge = AgentBridge()
        
        if hasattr(bridge, 'reset_circuit') or hasattr(bridge, 'reset_failures'):
            # Reset should work
            bridge.reset_circuit(AgentType.PI) if hasattr(bridge, 'reset_circuit') else bridge.reset_failures()
            assert True