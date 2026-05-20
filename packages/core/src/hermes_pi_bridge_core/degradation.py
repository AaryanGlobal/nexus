"""
Graceful Degradation - Component failure handling
Ensures system continues even when components fail
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Any, Optional
from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)


class ComponentState(Enum):
    """State of a component."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"


@dataclass
class ComponentHealth:
    """Health status of a component."""
    name: str
    state: ComponentState
    failures: int = 0
    last_failure: Optional[datetime] = None
    last_success: Optional[datetime] = None
    consecutive_failures: int = 0
    max_failures: int = 5  # Degrade after this
    recovery_interval: int = 60  # Try recovery after 60s


@dataclass
class FallbackResult:
    """Result from fallback action."""
    success: bool
    used_fallback: bool
    fallback_name: Optional[str] = None
    error: Optional[str] = None
    result: Any = None


class GracefulDegradation:
    """
    Handles component failures gracefully.
    
    Features:
    - Component health tracking
    - Automatic degradation after failures
    - Fallback actions
    - Auto-recovery attempts
    """
    
    def __init__(self):
        self.components: dict[str, ComponentHealth] = {}
        self.fallbacks: dict[str, Callable] = {}
    
    def register_component(self, name: str, max_failures: int = 5,
                          recovery_interval: int = 60):
        """Register a component for health tracking."""
        self.components[name] = ComponentHealth(
            name=name,
            state=ComponentState.HEALTHY,
            max_failures=max_failures,
            recovery_interval=recovery_interval
        )
    
    def register_fallback(self, component: str, fallback: Callable):
        """Register fallback action for component."""
        self.fallbacks[component] = fallback
    
    def call_with_fallback(self, component: str, action: Callable,
                          *args, **kwargs) -> FallbackResult:
        """Call action with fallback on failure."""
        health = self.components.get(component)
        
        # If component is failed and not recovering, use fallback immediately
        if health and health.state == ComponentState.FAILED:
            fallback = self.fallbacks.get(component)
            if fallback:
                try:
                    result = fallback(*args, **kwargs)
                    return FallbackResult(
                        success=True,
                        used_fallback=True,
                        fallback_name=component,
                        result=result
                    )
                except Exception as e:
                    return FallbackResult(
                        success=False,
                        used_fallback=True,
                        fallback_name=component,
                        error=str(e)
                    )
            else:
                return FallbackResult(
                    success=False,
                    used_fallback=False,
                    error=f"Component {component} is failed and no fallback available"
                )
        
        # Try main action
        try:
            result = action(*args, **kwargs)
            
            # Record success
            if health:
                health.failures = max(0, health.failures - 1)
                health.consecutive_failures = 0
                health.last_success = datetime.now()
                if health.state == ComponentState.DEGRADED:
                    health.state = ComponentState.HEALTHY
                    logger.info(f"Component {component} recovered")
            
            return FallbackResult(success=True, used_fallback=False, result=result)
            
        except Exception as e:
            # Record failure
            if health:
                health.failures += 1
                health.consecutive_failures += 1
                health.last_failure = datetime.now()
                
                if health.consecutive_failures >= health.max_failures:
                    health.state = ComponentState.FAILED
                    logger.warning(f"Component {component} failed: {e}")
                elif health.state == ComponentState.HEALTHY:
                    health.state = ComponentState.DEGRADED
                    logger.warning(f"Component {component} degraded: {e}")
            
            # Try fallback
            fallback = self.fallbacks.get(component)
            if fallback:
                try:
                    result = fallback(*args, **kwargs)
                    return FallbackResult(
                        success=True,
                        used_fallback=True,
                        fallback_name=component,
                        result=result
                    )
                except Exception as fe:
                    return FallbackResult(
                        success=False,
                        used_fallback=True,
                        fallback_name=component,
                        error=str(fe)
                    )
            
            return FallbackResult(success=False, used_fallback=False, error=str(e))
    
    def get_health(self, component: str) -> ComponentHealth | None:
        """Get health status of component."""
        return self.components.get(component)
    
    def get_all_health(self) -> dict[str, dict]:
        """Get all component health statuses."""
        result = {}
        for name, health in self.components.items():
            result[name] = {
                'state': health.state.value,
                'failures': health.failures,
                'consecutive_failures': health.consecutive_failures,
                'last_failure': health.last_failure.isoformat() if health.last_failure else None,
                'last_success': health.last_success.isoformat() if health.last_success else None,
            }
        return result
    
    def reset_component(self, component: str):
        """Manually reset a component to healthy."""
        if component in self.components:
            self.components[component].state = ComponentState.HEALTHY
            self.components[component].consecutive_failures = 0
            logger.info(f"Component {component} manually reset")
    
    def check_recovery(self, component: str) -> bool:
        """Check if component should attempt recovery."""
        health = self.components.get(component)
        if not health or health.state != ComponentState.FAILED:
            return False
        
        # Check if recovery interval has passed
        if health.last_failure:
            elapsed = (datetime.now() - health.last_failure).total_seconds()
            if elapsed >= health.recovery_interval:
                health.state = ComponentState.RECOVERING
                return True
        
        return False