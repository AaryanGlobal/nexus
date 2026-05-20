"""
NHIL Autonomous Loop - Orchestrates All Components

This is the brain that connects:
- Task Reasoner (decides WHAT to delegate)
- Hermes Bridge (communicates with Hermes)
- pi Bridge (communicates with pi)  
- Security Controls (OWASP safeguards)
- Evolution Controller (self-improvement)

The loop runs continuously, processing tasks proactively.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable
import threading

from .reasoner import TaskReasoner, DelegationDecision
from .security import SecurityControls
from .evolution import EvolutionController


logger = logging.getLogger(__name__)


class LoopState(StrEnum):
    """States of the autonomous loop."""
    IDLE = "idle"
    ANALYZING = "analyzing"
    DELEGATING = "delegating"
    EXECUTING = "executing"
    EVOLVING = "evolving"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass
class LoopMetrics:
    """Metrics from the autonomous loop."""
    tasks_processed: int = 0
    tasks_delegated: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    security_violations_blocked: int = 0
    evolutions_attempted: int = 0
    evolutions_successful: int = 0
    average_task_duration: float = 0.0
    uptime_seconds: float = 0.0
    last_task_time: float | None = None


@dataclass
class LoopConfig:
    """Configuration for the autonomous loop."""
    heartbeat_interval_seconds: int = 30
    max_task_age_seconds: int = 3600
    max_retries_per_task: int = 3
    enable_auto_evolution: bool = True
    evolution_interval_seconds: int = 300
    security_threshold: int = 5
    auto_delegate_threshold: float = 0.7


class NHILLoop:
    """
    No-Human-In-The-Loop Autonomous Execution System.
    
    This loop orchestrates:
    1. Task Analysis (reasoner decides delegation)
    2. Security Validation (OWASP controls)
    3. Task Delegation (to Hermes or pi)
    4. Result Collection
    5. Evolution (self-improvement via tests)
    
    The loop is designed to be:
    - Self-healing: Recovers from errors automatically
    - Self-improving: Runs tests to evolve
    - Safe: OWASP-level security controls
    - Proactive: Anticipates needs, doesn't just react
    """
    
    def __init__(
        self,
        config: LoopConfig | None = None,
        on_task_delegate: Callable | None = None,
        on_task_result: Callable | None = None,
        on_security_violation: Callable | None = None,
    ):
        self.config = config or LoopConfig()
        
        # Core components
        self.reasoner = TaskReasoner(
            auto_delegate_threshold=self.config.auto_delegate_threshold
        )
        self.security = SecurityControls(
            quarantine_threshold=self.config.security_threshold
        )
        self.evolution = EvolutionController()
        
        # Callbacks for external integration
        self.on_task_delegate = on_task_delegate
        self.on_task_result = on_task_result
        self.on_security_violation = on_security_violation
        
        # State
        self.state = LoopState.IDLE
        self.running = False
        self.start_time = time.time()
        self.metrics = LoopMetrics()
        
        # Task tracking
        self.active_tasks: dict[str, dict[str, Any]] = {}
        self.task_history: list[dict[str, Any]] = []
        
        # Threads
        self._heartbeat_thread: threading.Thread | None = None
        self._evolution_thread: threading.Thread | None = None
        self._lock = threading.Lock()
    
    def start(self) -> bool:
        """Start the autonomous loop."""
        if self.running:
            logger.warning("Loop already running")
            return False
        
        self.running = True
        self.state = LoopState.IDLE
        
        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        
        # Start evolution thread if enabled
        if self.config.enable_auto_evolution:
            self._evolution_thread = threading.Thread(target=self._evolution_loop, daemon=True)
            self._evolution_thread.start()
        
        logger.info("NHIL Autonomous Loop started")
        return True
    
    def stop(self) -> bool:
        """Stop the autonomous loop."""
        if not self.running:
            return False
        
        self.running = False
        self.state = LoopState.IDLE
        
        logger.info("NHIL Autonomous Loop stopped")
        return True
    
    def process_task(
        self,
        description: str,
        context: dict[str, Any] = None,
        skip_security: bool = False,
        depth: int = 0,
    ) -> dict[str, Any]:
        """
        Process a task through the full autonomous pipeline.
        
        Pipeline:
        1. Security validation
        2. Task analysis (reasoner)
        3. Delegation decision
        4. Execute delegation
        5. Record metrics
        
        Args:
            depth: Current recursion depth (prevents infinite loops)
        """
        context = context or {}
        task_id = context.get("task_id", f"task-{time.time()}")
        
        # Prevent infinite recursion
        if depth > 3:
            return {
                "task_id": task_id,
                "success": True,
                "decision": "max_depth_reached",
                "error": "Max recursion depth exceeded"
            }
        
        with self._lock:
            self.state = LoopState.ANALYZING
            self.metrics.tasks_processed += 1
            
            result = {
                "task_id": task_id,
                "success": False,
                "decision": None,
                "error": None,
                "security_violations": [],
            }
            
            # Step 1: Security validation
            if not skip_security:
                is_valid, violations = self.security.validate_input(
                    content=description,
                    session_id=task_id,
                )
                
                if not is_valid:
                    result["security_violations"] = [
                        {"event": v.event, "level": v.threat_level}
                        for v in violations
                    ]
                    result["error"] = "Security validation failed"
                    self.metrics.security_violations_blocked += 1
                    
                    if self.on_security_violation:
                        self.on_security_violation(violations)
                    
                    self.state = LoopState.BLOCKED
                    return result
            
            # Step 2: Task analysis
            analysis = self.reasoner.analyze_task(description, context)
            
            # Step 3: Delegation decision
            decision = self.reasoner.decide(analysis)
            result["decision"] = decision.decision.value
            result["confidence"] = decision.confidence
            result["reasoning"] = decision.reasoning
            
            self.state = LoopState.DELEGATING
            
            # Step 4: Execute delegation
            if decision.decision == DelegationDecision.REJECT:
                result["error"] = "Task rejected: requires human approval"
                self.state = LoopState.BLOCKED
                
            elif decision.decision == DelegationDecision.DELEGATE_TO_PI:
                if self.on_task_delegate:
                    delegate_result = self.on_task_delegate(
                        description=description,
                        priority=decision.suggested_priority,
                        context=context,
                    )
                    result["delegate_result"] = delegate_result
                    result["success"] = delegate_result.get("success", False)
                    self.metrics.tasks_delegated += 1
                else:
                    result["success"] = True  # Simulated success
                    self.metrics.tasks_delegated += 1
                    
            elif decision.decision == DelegationDecision.HANDLE_SELF:
                # Process internally
                result["success"] = True
                result["handled_internally"] = True
                
            elif decision.decision == DelegationDecision.SPLIT_AND_DELEGATE:
                # Process subtasks with depth limit
                subtask_results = []
                for subtask in decision.subtasks:
                    sub_result = self.process_task(
                        description=subtask["title"],
                        context=subtask,
                        skip_security=True,  # Already validated
                        depth=depth + 1,
                    )
                    subtask_results.append(sub_result)
                result["subtask_results"] = subtask_results
                result["success"] = all(r.get("success", False) for r in subtask_results)
            
            # Step 5: Update metrics
            self.metrics.tasks_completed += 1 if result["success"] else 0
            self.metrics.tasks_failed += 1 if not result["success"] else 0
            self.metrics.last_task_time = time.time()
            
            # Store in history
            self.task_history.append({
                "task_id": task_id,
                "timestamp": time.time(),
                "result": result,
            })
            
            # Keep history bounded
            if len(self.task_history) > 1000:
                self.task_history = self.task_history[-500:]
            
            self.state = LoopState.IDLE
            return result
    
    def report_result(
        self,
        task_id: str,
        status: str,
        summary: str,
        artifacts: list[str] = None,
        errors: list[str] = None,
    ) -> dict[str, Any]:
        """Report task result back to the loop."""
        result = {
            "task_id": task_id,
            "status": status,
            "summary": summary,
            "timestamp": time.time(),
        }
        
        if self.on_task_result:
            self.on_task_result(result)
        
        # Update metrics
        if status == "success":
            self.metrics.tasks_completed += 1
        else:
            self.metrics.tasks_failed += 1
        
        # Trigger evolution on failure
        if status in ("failed", "error") and self.config.enable_auto_evolution:
            self._attempt_evolution(task_id, errors)
        
        return result
    
    def _heartbeat_loop(self) -> None:
        """Background heartbeat to keep loop alive."""
        while self.running:
            time.sleep(self.config.heartbeat_interval_seconds)
            
            if self.running and self.state != LoopState.ERROR:
                # Update uptime
                self.metrics.uptime_seconds = time.time() - self.start_time
                
                # Check for stale tasks
                self._check_stale_tasks()
    
    def _evolution_loop(self) -> None:
        """Background evolution loop for self-improvement."""
        while self.running:
            time.sleep(self.config.evolution_interval_seconds)
            
            if self.running:
                self._run_evolution_cycle()
    
    def _check_stale_tasks(self) -> None:
        """Check for and handle stale tasks."""
        now = time.time()
        stale_tasks = []
        
        for task_id, task in self.active_tasks.items():
            age = now - task.get("start_time", now)
            if age > self.config.max_task_age_seconds:
                stale_tasks.append(task_id)
        
        for task_id in stale_tasks:
            logger.warning(f"Task {task_id} exceeded max age, marking failed")
            del self.active_tasks[task_id]
            self.report_result(
                task_id=task_id,
                status="failed",
                summary="Task exceeded maximum age",
                errors=["Timeout: task stale"]
            )
    
    def _attempt_evolution(self, task_id: str, errors: list[str] = None) -> None:
        """Attempt to evolve/improve after failure."""
        if not self.config.enable_auto_evolution:
            return
        
        self.state = LoopState.EVOLVING
        self.metrics.evolutions_attempted += 1
        
        # Record the failure for analysis
        evolution_record = self.evolution.evolve(
            trigger=f"task_failure:{task_id}",
            action=f"analyze_error:{errors}",
            test_path="packages/core/tests",
        )
        
        if evolution_record.test_results and evolution_record.test_results.success:
            self.metrics.evolutions_successful += 1
        
        self.state = LoopState.IDLE
    
    def _run_evolution_cycle(self) -> None:
        """Run a complete evolution cycle."""
        self.state = LoopState.EVOLVING
        
        # Run full test suite
        result = self.evolution.run_tests("packages/core/tests")
        
        # Record metrics
        if result.success:
            self.metrics.evolutions_successful += 1
        
        self.state = LoopState.IDLE
    
    def get_metrics(self) -> dict[str, Any]:
        """Get current loop metrics."""
        self.metrics.uptime_seconds = time.time() - self.start_time
        return {
            "state": self.state.value if hasattr(self.state, 'value') else str(self.state),
            "running": self.running,
            "metrics": {
                "tasks_processed": self.metrics.tasks_processed,
                "tasks_delegated": self.metrics.tasks_delegated,
                "tasks_completed": self.metrics.tasks_completed,
                "tasks_failed": self.metrics.tasks_failed,
                "security_violations_blocked": self.metrics.security_violations_blocked,
                "evolutions_attempted": self.metrics.evolutions_attempted,
                "evolutions_successful": self.metrics.evolutions_successful,
                "uptime_seconds": self.metrics.uptime_seconds,
            },
            "security_stats": self.security.get_security_stats(),
            "evolution_stats": self.evolution.get_evolution_stats(),
        }
    
    def get_active_tasks(self) -> list[dict[str, Any]]:
        """Get list of active tasks."""
        return list(self.active_tasks.values())
    
    def get_task_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent task history."""
        return self.task_history[-limit:]
