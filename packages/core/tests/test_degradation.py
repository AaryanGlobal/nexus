"""TDD: Graceful Degradation Tests"""
import pytest
from datetime import datetime

from hermes_pi_bridge_core.degradation import (
    GracefulDegradation, ComponentHealth, FallbackResult, ComponentState
)


@pytest.fixture
def degrader():
    """Create test degrader."""
    return GracefulDegradation()


class TestComponentRegistration:
    """Test component registration."""
    
    def test_register_component(self, degrader):
        """Can register a component."""
        degrader.register_component("scanner")
        health = degrader.get_health("scanner")
        assert health is not None
        assert health.state == ComponentState.HEALTHY
    
    def test_register_with_config(self, degrader):
        """Can configure max_failures."""
        degrader.register_component("scanner", max_failures=3)
        health = degrader.get_health("scanner")
        assert health.max_failures == 3


class TestFallbackAction:
    """Test fallback execution."""
    
    def test_successful_call(self, degrader):
        """Successful call returns result."""
        degrader.register_component("test")
        result = degrader.call_with_fallback("test", lambda: "success")
        assert result.success is True
        assert result.used_fallback is False
        assert result.result == "success"
    
    def test_fallback_on_failure(self, degrader):
        """Calls fallback on component failure."""
        degrader.register_component("test", max_failures=1)
        
        # First call fails
        def fail():
            raise ValueError("Test failure")
        
        def fallback():
            return "fallback_result"
        
        degrader.register_fallback("test", fallback)
        
        result = degrader.call_with_fallback("test", fail)
        assert result.success is True
        assert result.used_fallback is True
        assert result.result == "fallback_result"
    
    def test_no_fallback_available(self, degrader):
        """Returns error when no fallback."""
        degrader.register_component("test", max_failures=1)
        
        def fail():
            raise ValueError("Test failure")
        
        result = degrader.call_with_fallback("test", fail)
        assert result.success is False
        assert result.error is not None


class TestDegradationState:
    """Test degradation states."""
    
    def test_degrades_after_failures(self, degrader):
        """Component degrades after consecutive failures."""
        degrader.register_component("test", max_failures=2)
        
        for _ in range(2):
            try:
                degrader.call_with_fallback("test", lambda: (_ for _ in ()).throw(Exception("fail")))
            except:
                pass
        
        health = degrader.get_health("test")
        assert health.consecutive_failures == 2
    
    def test_recovery_on_success(self, degrader):
        """Health recovers after success."""
        degrader.register_component("test", max_failures=2)
        
        degrader.call_with_fallback("test", lambda: "ok")
        
        health = degrader.get_health("test")
        assert health.consecutive_failures == 0
        assert health.state == ComponentState.HEALTHY


class TestGetAllHealth:
    """Test health reporting."""
    
    def test_get_all_health(self, degrader):
        """Returns all component health."""
        degrader.register_component("scanner")
        degrader.register_component("executor")
        
        health = degrader.get_all_health()
        assert "scanner" in health
        assert "executor" in health
        assert health["scanner"]["state"] == "healthy"


class TestReset:
    """Test manual reset."""
    
    def test_manual_reset(self, degrader):
        """Can manually reset component."""
        degrader.register_component("test", max_failures=1)
        
        # Force to degraded state
        try:
            degrader.call_with_fallback("test", lambda: (_ for _ in ()).throw(Exception("fail")))
        except:
            pass
        
        degrader.reset_component("test")
        health = degrader.get_health("test")
        assert health.state == ComponentState.HEALTHY
        assert health.consecutive_failures == 0