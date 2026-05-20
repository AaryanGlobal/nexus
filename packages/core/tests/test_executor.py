"""TDD: Safe Executor Tests"""
import pytest
import os
import time
from hermes_pi_bridge_core.executor import (
    SafeExecutor, ExecutionConfig, ExecutionResult
)


class TestSecurityChecks:
    """Test security checks on commands."""
    
    def test_blocks_dangerous_patterns(self):
        executor = SafeExecutor()
        result = executor.execute("rm -rf /")
        assert result.success is False
    
    def test_blocks_sudo(self):
        executor = SafeExecutor()
        result = executor.execute("sudo rm -rf /")
        assert result.success is False
        assert result.error is not None
    
    def test_allows_safe_commands(self):
        executor = SafeExecutor()
        result = executor.execute("echo 'hello world'")
        assert result.success is True
        assert "hello world" in result.stdout


class TestExecution:
    """Test command execution."""
    
    def test_simple_echo(self):
        executor = SafeExecutor()
        result = executor.execute("echo test")
        assert result.success is True
    
    def test_exit_code_captured(self):
        executor = SafeExecutor()
        result = executor.execute("exit 42")
        assert result.exit_code == 42
    
    def test_empty_command_rejected(self):
        executor = SafeExecutor()
        result = executor.execute("")
        assert result.success is False


class TestTimeouts:
    """Test timeout enforcement."""
    
    def test_timeout_enforced(self):
        config = ExecutionConfig(max_duration_seconds=1)
        executor = SafeExecutor(config=config)
        result = executor.execute("sleep 10")
        assert result.success is False


class TestScriptExecution:
    """Test script execution."""
    
    def test_execute_python_script(self):
        executor = SafeExecutor()
        script = "print('hello from python')"
        result = executor.execute_script(script, language="python")
        assert result.success is True
    
    def test_unsupported_language(self):
        executor = SafeExecutor()
        result = executor.execute_script("code", language="ruby")
        assert result.success is False


class TestExecutionHistory:
    """Test execution history tracking."""
    
    def test_history_tracked(self):
        executor = SafeExecutor()
        executor.execute("echo test1")
        executor.execute("echo test2")
        stats = executor.get_execution_stats()
        assert stats["total_executions"] == 2


class TestEdgeCases:
    """Test edge cases."""
    
    def test_command_with_pipes(self):
        executor = SafeExecutor()
        result = executor.execute("echo 'hello' | grep hello")
        assert result.success is True
    
    def test_multiple_executions(self):
        executor = SafeExecutor()
        for i in range(3):
            r = executor.execute(f"echo {i}")
            assert r.success is True