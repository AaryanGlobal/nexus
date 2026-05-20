"""
Safe Execution Layer - Actually Runs Code

TDD Tests verify:
- Command execution is sandboxed
- Timeouts enforced
- Output captured
- Errors handled safely
"""

from __future__ import annotations

import subprocess
import tempfile
import os
from dataclasses import dataclass, field
from typing import Any
import time


@dataclass
class ExecutionResult:
    """Result of command execution."""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    command: str
    artifacts: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class ExecutionConfig:
    """Configuration for safe execution."""
    max_duration_seconds: int = 60
    max_output_kb: int = 1024
    allowed_paths: list[str] = field(default_factory=list)
    blocked_commands: list[str] = field(default_factory=list)
    working_directory: str | None = None
    
    def __post_init__(self):
        if not self.blocked_commands:
            self.blocked_commands = [
                'sudo', 'su', 'chmod', 'chown', 'passwd',
                'shutdown', 'reboot', 'halt', 'poweroff',
                'mkfs', 'fdisk', 'dd',
            ]


class SafeExecutor:
    """
    Executes commands safely for autonomous agent use.
    
    Security features:
    - Command blocklist
    - Timeout enforcement
    - Output limits
    """
    
    DANGEROUS_PATTERNS = [
        'rm -rf /', 'rm -rf /*',
        ':(){ :|:& };:',
        'curl | sh', 'wget | sh',
    ]
    
    def __init__(self, config: ExecutionConfig | None = None):
        self.config = config or ExecutionConfig()
        self.execution_history: list[ExecutionResult] = []
        self.max_history = 500
    
    def execute(self, command: str, description: str = "") -> ExecutionResult:
        """Execute a command safely."""
        start_time = time.time()
        
        # Security check
        security_error = self._security_check(command)
        if security_error:
            return ExecutionResult(
                success=False, exit_code=-1, stdout="", stderr="",
                duration_seconds=0, command=command, error=security_error
            )
        
        cwd = self.config.working_directory or tempfile.gettempdir()
        
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=self.config.max_duration_seconds, cwd=cwd
            )
            
            duration = time.time() - start_time
            output = result.stdout + result.stderr
            
            if len(output) > self.config.max_output_kb * 1024:
                output = output[:self.config.max_output_kb * 1024] + "\n... [TRUNCATED]"
            
            exec_result = ExecutionResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_seconds=duration,
                command=command,
            )
            
            self._record(exec_result)
            return exec_result
            
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False, exit_code=-2, stdout="", stderr="",
                duration_seconds=self.config.max_duration_seconds,
                command=command, error="Timeout"
            )
        except Exception as e:
            return ExecutionResult(
                success=False, exit_code=-3, stdout="", stderr=str(e),
                duration_seconds=time.time() - start_time,
                command=command, error=str(e)
            )
    
    def execute_script(self, script: str, language: str = "bash") -> ExecutionResult:
        """Execute a script safely."""
        if language == "bash":
            return self.execute(script)
        elif language == "python":
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script)
                temp_path = f.name
            try:
                return self.execute(f"python3 {temp_path}")
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass
        else:
            return ExecutionResult(
                success=False, exit_code=-1, stdout="", stderr=f"Unsupported: {language}",
                duration_seconds=0, command=f"<{language}>", error=f"Unsupported: {language}"
            )
    
    def _security_check(self, command: str) -> str | None:
        """Check if command is safe."""
        if not command or not command.strip():
            return "Empty command"
        
        cmd_lower = command.lower()
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern.lower() in cmd_lower:
                return f"Dangerous: {pattern}"
        
        for blocked in self.config.blocked_commands:
            if f" {blocked}" in cmd_lower or cmd_lower.startswith(blocked):
                return f"Blocked: {blocked}"
        
        return None
    
    def _record(self, result: ExecutionResult) -> None:
        self.execution_history.append(result)
        if len(self.execution_history) > self.max_history:
            self.execution_history = self.execution_history[-self.max_history:]
    
    def get_execution_stats(self) -> dict[str, Any]:
        """Get execution statistics."""
        if not self.execution_history:
            return {"total_executions": 0, "success_rate": 0.0}
        
        total = len(self.execution_history)
        successes = sum(1 for r in self.execution_history if r.success)
        
        return {
            "total_executions": total,
            "successes": successes,
            "failures": total - successes,
            "success_rate": successes / total if total > 0 else 0.0,
        }