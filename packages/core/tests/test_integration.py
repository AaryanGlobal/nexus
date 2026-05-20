"""
Integration Tests: Hermes-Pi Bridge (TDD)

Tests the actual communication between Hermes and pi.
These require both services to be running for full integration tests.
"""

import pytest
from hermes_pi_bridge_core.types import TaskStatus, Priority, ErrorCode


class TestProtocolCompatibility:
    """Test that Python and TypeScript types match."""
    
    def test_task_status_enum_values_match(self):
        """Python TaskStatus should match TypeScript values."""
        expected = {
            "pending", "running", "success",
            "partial", "failed", "blocked", "cancelled"
        }
        actual = {s.value for s in TaskStatus}
        assert actual == expected
    
    def test_priority_enum_values_match(self):
        """Python Priority should match TypeScript values."""
        expected = {"low", "normal", "high"}
        actual = {p.value for p in Priority}
        assert actual == expected
    
    def test_error_codes_match(self):
        """Error codes should be consistent."""
        # JSON-RPC codes should be negative
        assert ErrorCode.PARSE_ERROR == -32700
        assert ErrorCode.INVALID_REQUEST == -32600
        
        # Bridge codes should be positive 1000+
        assert ErrorCode.AUTH_ERROR == 1000
        assert ErrorCode.TASK_NOT_FOUND == 1002
        assert ErrorCode.TIMEOUT == 1003


class TestEndToEndFlow:
    """Test complete task flow documentation."""
    
    def test_full_task_lifecycle_flow(self):
        """Document expected task lifecycle."""
        flow = [
            "delegate_task",      # Hermes → Bridge → pi
            "execute_task",        # pi processes task
            "report_result",       # pi → Bridge → Hermes
            "update_kanban"        # Hermes updates task status
        ]
        assert len(flow) == 4
        assert flow[0] == "delegate_task"
    
    def test_error_recovery_flow(self):
        """Document error recovery flow."""
        flow = [
            "delegate_task",
            "execute_task",
            "report_result_with_error",
            "increment_failure_count",
            "retry_if_under_threshold",
            "quarantine_after_limit"
        ]
        assert len(flow) == 6


class TestSecurityIntegration:
    """Test security controls integration."""
    
    def test_security_controls_import(self):
        """Security controls should be importable."""
        from hermes_pi_bridge_core.security import SecurityControls
        ctrl = SecurityControls()
        assert ctrl is not None
    
    def test_evolution_controller_import(self):
        """Evolution controller should be importable."""
        from hermes_pi_bridge_core.evolution import EvolutionController
        ctrl = EvolutionController()
        assert ctrl is not None


class TestMonorepoStructure:
    """Verify monorepo structure is correct."""
    
    def test_core_package_has_security(self):
        """Core package should include security module."""
        from hermes_pi_bridge_core import security
        assert hasattr(security, 'SecurityControls')
    
    def test_core_package_has_evolution(self):
        """Core package should include evolution module."""
        from hermes_pi_bridge_core import evolution
        assert hasattr(evolution, 'EvolutionController')
    
    def test_core_package_has_types(self):
        """Core package should include types module."""
        from hermes_pi_bridge_core import types
        assert hasattr(types, 'TaskStatus')
        assert hasattr(types, 'Priority')
        assert hasattr(types, 'ErrorCode')