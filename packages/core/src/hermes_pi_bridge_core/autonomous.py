"""
AutonomousNHIL - Fully Self-Sufficient Autonomous Agent

TDD: All gaps addressed via tests.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from .loop import NHILLoop, LoopConfig
from .learning import PatternLearner
from .persistence import PersistenceManager, PersistedState
from .reasoner import TaskReasoner
from .security import SecurityControls, SecurityConfig
from .evolution import EvolutionController
from .executor import SafeExecutor, ExecutionConfig
from .scanner import WorkScanner, ScanConfig, DiscoveredTask
from .goals import GoalManager, GoalStatus, GoalPriority
from .governance import BridgeGovernance, GovernanceConfig, DecisionType, DecisionConfidence
from .rl import ReinforcementLearning, RLConfig, ActionType
from .rate_limiter import RateLimiter, RateLimitConfig
from .life_context import LifeContextEngine
from .config import NexusConfig, get_config
from .degradation import GracefulDegradation
from .bridge import AgentBridge, AgentType, get_bridge
from pathlib import Path


logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """An audit log entry."""
    timestamp: float
    action: str
    details: str
    user: str = "system"
    result: str = "success"


@dataclass
class AutonomousConfig:
    """Configuration for the autonomous agent."""
    storage_path: str = "~/.autonomous-nhil/state.json"
    scan_interval_seconds: int = 300
    scan_paths: list[str] = None
    max_execution_duration_seconds: int = 60
    enable_learning: bool = True
    max_history_entries: int = 1000
    enable_evolution: bool = True
    evolution_threshold: int = 3
    strict_mode: bool = True
    
    def __post_init__(self):
        if self.scan_paths is None:
            from pathlib import Path
            self.scan_paths = [str(Path.home() / "projects"), str(Path.home() / "work")]
        
        # Validate values
        if self.scan_interval_seconds < 0:
            self.scan_interval_seconds = 300
        if self.max_execution_duration_seconds <= 0:
            self.max_execution_duration_seconds = 60


class AutonomousNHIL:
    """
    Fully autonomous NHIL agent with self-evolution and user control.
    
    Methods for user control:
    - start() / stop() - lifecycle
    - pause() / resume() - control processing
    - inject_task() - manually add tasks
    - approve_task() / reject_task() - approve/discover work
    - override_decision() - force actions
    - get_status() / get_current_activity() - monitoring
    - get_audit_log() - audit trail
    - ask() - query the agent
    """
    
    def __init__(self, config: AutonomousConfig | None = None, task_callback: Callable | None = None):
        # Load centralized config
        self.nexus_config = get_config()
        
        self.config = config or AutonomousConfig()
        self.task_callback = task_callback
        self._audit_log: list[AuditEntry] = []
        self._paused = False
        
        # GOAL MANAGEMENT - The common space for user needs
        goals_path = self.nexus_config.storage.get_path(self.nexus_config.storage.goals_file)
        self.goals = GoalManager(storage_path=str(goals_path))
        
        self._init_components()
        self.running = False
        self.main_loop_thread: threading.Thread | None = None
        logger.info("AutonomousNHIL initialized")
    
    def _init_components(self) -> None:
        """Initialize all components."""
        self.persistence = PersistenceManager(self.config.storage_path)
        self.previous_state = self.persistence.load()
        
        self.learner = PatternLearner()
        
        # GOVERNANCE - Check/balance mechanism for the bridge
        gov_config = GovernanceConfig()
        self.governance = BridgeGovernance(gov_config)
        
        # RL - Rewards and punishments for learning
        # Use RLConfig from rl module with defaults
        rl_config = RLConfig(
            learning_rate=self.nexus_config.rl.learning_rate,
            discount_factor=self.nexus_config.rl.discount_factor,
            exploration_rate=self.nexus_config.rl.exploration_rate,
        )
        self.rl = ReinforcementLearning(rl_config)
        
        # RATE LIMITER - Use centralized config
        self.rate_limiter = RateLimiter(self.nexus_config.rate_limit)
        
        # LIFE CONTEXT ENGINE - Use centralized storage path
        life_path = str(self.nexus_config.storage.get_path(self.nexus_config.storage.life_context_file))
        self.life_context = LifeContextEngine(storage_path=life_path)
        
        security_config = SecurityConfig(strict_mode=self.config.strict_mode)
        self.security = SecurityControls(security_config)
        
        exec_config = ExecutionConfig(max_duration_seconds=self.config.max_execution_duration_seconds)
        self.executor = SafeExecutor(exec_config)
        
        # SCANNER - Use centralized config
        scan_config = ScanConfig(
            scan_paths=self.config.scan_paths,
            scan_interval_seconds=self.nexus_config.scanner.scan_interval_seconds
        )
        self.scanner = WorkScanner(scan_config)
        
        self.reasoner = TaskReasoner()
        self.evolution = EvolutionController()
        
        # LOOP - Use governance config from centralized config
        loop_config = LoopConfig(
            enable_auto_evolution=self.config.enable_evolution,
            heartbeat_interval_seconds=30
        )
        self.loop = NHILLoop(
            config=loop_config,
            on_task_delegate=self._delegate_task,
            on_task_result=self._handle_result,
            on_security_violation=self._handle_security_violation,
        )
        
        # GRACEFUL DEGRADATION - Handle component failures
        self.degradation = GracefulDegradation()
        self._register_degradation_handlers()
        
        # AGENT BRIDGE - Communication with Hermes and PI
        self.agent_bridge = get_bridge()
        
        self.tasks_discovered = 0
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.start_time = time.time()
    
    def _register_degradation_handlers(self):
        """Register components for health tracking."""
        self.degradation.register_component("scanner", max_failures=3, recovery_interval=60)
        self.degradation.register_component("executor", max_failures=3, recovery_interval=60)
        self.degradation.register_component("governance", max_failures=2, recovery_interval=120)
        self.degradation.register_component("rl", max_failures=2, recovery_interval=120)
    
    def _safe_call(self, component: str, action: Callable, *args, **kwargs) -> Any:
        """Call action with graceful degradation."""
        result = self.degradation.call_with_fallback(component, action, *args, **kwargs)
        if not result.success and result.error:
            logger.warning(f"{component} failed: {result.error}")
        return result
    
    # === USER CONTROL METHODS ===
    
    def start(self) -> bool:
        """Start the agent."""
        if self.running:
            logger.warning("Agent already running")
            return False
        
        self.loop.start()
        self.running = True
        self._paused = False
        self.main_loop_thread = threading.Thread(target=self._main_loop, daemon=True)
        self.main_loop_thread.start()
        logger.info("AutonomousNHIL started")
        return True
    
    def stop(self) -> bool:
        """Stop the agent."""
        if not self.running:
            return False
        
        self.running = False
        self.loop.stop()
        self._save_state()
        
        if self.main_loop_thread:
            self.main_loop_thread.join(timeout=5)
        
        logger.info("AutonomousNHIL stopped")
        return True
    
    def pause(self) -> None:
        """Pause the agent."""
        if self.running:
            self._paused = True
            self._audit_log.append(AuditEntry(time.time(), 'pause', 'Agent paused', 'user'))
            logger.info("Agent paused")
    
    def resume(self) -> None:
        """Resume the agent."""
        self._paused = False
        self._audit_log.append(AuditEntry(time.time(), 'resume', 'Agent resumed', 'user'))
        logger.info("Agent resumed")
    
    @property
    def is_paused(self) -> bool:
        return self._paused
    
    @property
    def is_running(self) -> bool:
        return self.running
    
    def inject_task(self, description: str, priority: str = "medium", context: dict = None) -> dict:
        """Manually inject a task."""
        context = context or {}
        context['injected'] = True
        context['priority_override'] = priority
        
        self._audit_log.append(AuditEntry(
            time.time(), 'inject_task', f"Injected: {description[:50]}", 'user'
        ))
        
        result = self.loop.process_task(description, context)
        
        # Update metrics based on result
        if result.get('success'):
            self.tasks_completed += 1
        else:
            self.tasks_failed += 1
        
        # Learn from task outcome
        duration = result.get('duration', 0)
        success = result.get('success', False)
        decision = result.get('decision', 'unknown')
        
        # Extract capabilities from description
        capabilities = self._extract_capabilities(description)
        self.learner.learn_from_task(description, decision, success, duration, capabilities)
        
        return result
    
    def _extract_capabilities(self, description: str) -> list[str]:
        """Extract capability keywords from description."""
        keywords = {
            'debug': ['debug', 'fix', 'bug', 'error', 'crash'],
            'test': ['test', 'testing', 'unit test'],
            'build': ['build', 'compile', 'make'],
            'deploy': ['deploy', 'release', 'publish'],
            'code': ['write', 'implement', 'create', 'code'],
        }
        
        desc_lower = description.lower()
        found = []
        for cap, words in keywords.items():
            if any(w in desc_lower for w in words):
                found.append(cap)
        return found
    
    def approve_task(self, task_description: str) -> dict:
        """Approve a discovered task."""
        self._audit_log.append(AuditEntry(
            time.time(), 'approve_task', f"Approved: {task_description[:50]}", 'user'
        ))
        return self.inject_task(task_description, priority='high')
    
    def reject_task(self, task_description: str, reason: str = "") -> dict:
        """Reject a discovered task."""
        self._audit_log.append(AuditEntry(
            time.time(), 'reject_task', f"Rejected: {reason}", 'user'
        ))
        return {'success': True, 'rejected': True, 'reason': reason}
    
    def override_decision(self, action: str, reason: str = "") -> dict:
        """Override decision - force action."""
        self._audit_log.append(AuditEntry(
            time.time(), 'override', f"Forced: {action} ({reason})", 'user'
        ))
        logger.info(f"User override: {action}")
        return {'success': True, 'action': action, 'reason': reason, 'override': True}
    
    def add_ideation(self, content: str) -> list:
        """Add goals from ideation (common space)."""
        self._audit_log.append(AuditEntry(
            time.time(), 'add_ideation', f"Added {len(self.goals.add_ideation(content))} goals", 'user'
        ))
        return self.goals.goals
    
    def get_suggestions(self) -> list[str]:
        """Get AI suggestions based on goals and learnings."""
        return self.goals.generate_suggestions()
    
    def get_next_goal(self) -> Any:
        """Get the next goal to work on."""
        return self.goals.get_next_goal()
    
    def work_on_goal(self, goal_id: str = None) -> dict:
        """Start working on a goal (or next available)."""
        if goal_id:
            goal = self.goals.work_on_goal(goal_id)
        else:
            goal = self.goals.get_next_goal()
            if goal:
                self.goals.work_on_goal(goal.id)
        
        if goal:
            return {'success': True, 'goal_id': goal.id, 'title': goal.title}
        return {'success': False, 'error': 'No goals available'}
    
    def update_goal_progress(self, goal_id: str, progress: float) -> dict:
        """Update progress on a goal."""
        goal = self.goals.update_goal_progress(goal_id, progress)
        if goal:
            return {'success': True, 'progress': goal.progress}
        return {'success': False}
    
    def get_goals_status(self) -> dict:
        """Get status of all goals."""
        return self.goals.get_status_summary()
    
    # === GOVERNANCE METHODS - Check/Balance Mechanism ===
    
    def validate_action(self, action_type: str, description: str, context: dict = None) -> dict:
        """
        Validate an action before execution.
        Returns validation result with confidence.
        """
        context = context or {}
        context['action_type'] = action_type
        
        # Map string to DecisionType
        action_mapping = {
            'execute': DecisionType.EXECUTE_TASK,
            'delegate': DecisionType.DELEGATE_TASK,
            'rollback': DecisionType.ROLLBACK,
            'split': DecisionType.SPLIT_TASK,
            'escalate': DecisionType.ESCALATE,
            'approve': DecisionType.APPROVE_WORK,
            'reject': DecisionType.REJECT_WORK,
        }
        
        decision_type = action_mapping.get(action_type, DecisionType.EXECUTE_TASK)
        decision, should_proceed = self.governance.validate_decision(decision_type, description, context)
        
        return {
            'validated': True,
            'decision_id': decision.id,
            'confidence': decision.confidence.value,
            'should_proceed': should_proceed,
            'reasoning': decision.reasoning
        }
    
    def approve_action(self, decision_id: str, approver: str = 'user') -> bool:
        """Approve a low-confidence action."""
        return self.governance.approve_decision(decision_id, approver)
    
    def execute_validated_action(self, decision_id: str, executor: Callable) -> Any:
        """Execute a validated action."""
        return self.governance.execute_decision(decision_id, executor)
    
    def create_checkpoint(self, description: str, state: dict = None) -> str:
        """Create a rollback checkpoint."""
        state = state or {'goals': len(self.goals.goals), 'tasks_completed': self.tasks_completed}
        return self.governance.create_rollback_point(description, state, lambda: None)
    
    def rollback_to_checkpoint(self, steps: int = 1) -> list:
        """Rollback to previous checkpoint."""
        return self.governance.rollback(steps)
    
    def run_tdd_cycle(self, test_code: str, implementation_code: str) -> dict:
        """
        Run a TDD cycle.
        - test_code: The failing test
        - implementation_code: The code to make it pass
        """
        def test_func():
            exec(test_code, {'__name__': '__test__'})
        
        def code_func():
            exec(implementation_code)
        
        return self.governance.run_tdd_cycle(test_func, code_func)
    
    def get_governance_status(self) -> dict:
        """Get governance dashboard status."""
        return self.governance.get_governance_report()
    
    def get_decision_confidence(self, decision_type: str) -> float:
        """Get confidence score for a decision type."""
        mapping = {
            'execute': DecisionType.EXECUTE_TASK,
            'delegate': DecisionType.DELEGATE_TASK,
            'rollback': DecisionType.ROLLBACK,
            'split': DecisionType.SPLIT_TASK,
            'escalate': DecisionType.ESCALATE,
            'approve': DecisionType.APPROVE_WORK,
            'reject': DecisionType.REJECT_WORK,
        }
        
        dt = mapping.get(decision_type, DecisionType.EXECUTE_TASK)
        return self.governance.get_confidence_score(dt)
    
    def circuit_breaker_status(self) -> dict:
        """Get circuit breaker status."""
        report = self.governance.get_governance_report()
        return {
            'open': report['circuit_open'],
            'failures': report['consecutive_failures'],
            'threshold': 5  # Default
        }
    
    def reset_circuit_breaker(self) -> bool:
        """Reset the circuit breaker."""
        self.governance.reset_circuit()
        return True
    
    # === RL METHODS - Rewards and Punishments ===
    
    def get_rl_action(self, state: str, context: dict = None) -> dict:
        """
        Get RL-based action recommendation.
        Uses epsilon-greedy exploration/exploitation.
        """
        context = context or {}
        action, confidence = self.rl.select_action(state, context)
        
        return {
            'action': action.value,
            'confidence': confidence,
            'state': state,
            'exploration': self.rl.config.exploration_rate
        }
    
    def apply_reward(self, action_type: str, success: bool, 
                    duration: float = 0, efficiency: float = 0,
                    context: str = "default") -> float:
        """
        Apply reward or punishment based on action outcome.
        Returns the reward received.
        """
        # Map string to ActionType
        action_mapping = {
            'execute': ActionType.EXECUTE,
            'delegate': ActionType.DELEGATE,
            'split': ActionType.SPLIT,
            'rollback': ActionType.ROLLBACK,
            'escalate': ActionType.ESCALATE,
            'skip': ActionType.SKIP,
        }
        
        action = action_mapping.get(action_type, ActionType.EXECUTE)
        reward = self.rl.reward(action, success, duration, efficiency, context)
        
        # Adjust exploration based on success rate
        stats = self.rl.get_statistics()
        total_actions = sum(stats['actions_taken'].values())
        if total_actions > 0:
            successes = sum([v for k, v in stats['success_rate'].items()]) * total_actions / len(ActionType)
            success_rate = successes / total_actions if total_actions > 0 else 0.5
            self.rl.adjust_exploration(success_rate)
        
        return reward
    
    def get_rl_policy(self, state: str) -> dict:
        """Get RL policy for a state."""
        policy = self.rl.get_policy(state)
        return {
            'recommended_action': policy['action'].value if policy['action'] else None,
            'confidence': policy['confidence'],
            'q_values': policy['q_values']
        }
    
    def get_rl_statistics(self) -> dict:
        """Get RL learning statistics."""
        return self.rl.get_statistics()
    
    def reset_rl(self):
        """Reset RL learning (start fresh)."""
        self.rl.reset()
    
    def set_exploration_rate(self, rate: float):
        """Set exploration rate (0-1)."""
        self.rl.config.exploration_rate = max(0, min(1, rate))
    
    def get_exploration_rate(self) -> float:
        """Get current exploration rate."""
        return self.rl.config.exploration_rate
    
    # === RATE LIMITER METHODS ===
    
    def check_rate_limit(self, provider: str = "default") -> dict:
        """Check if request can proceed."""
        can_proceed, reason = self.rate_limiter.can_proceed(provider)
        return {
            'can_proceed': can_proceed,
            'reason': reason,
            'wait_time': self.rate_limiter.get_wait_time(provider)
        }
    
    def record_api_request(self, success: bool, status_code: int = None,
                          provider: str = "default", endpoint: str = ""):
        """Record an API request for rate limiting."""
        self.rate_limiter.record_request(success, status_code, provider, endpoint)
    
    def get_rate_limit_status(self) -> dict:
        """Get comprehensive rate limit status."""
        return self.rate_limiter.get_status()
    
    def wait_if_needed(self, provider: str = "default") -> float:
        """Wait if rate limited. Returns wait time."""
        wait = self.rate_limiter.get_wait_time(provider)
        if wait > 0:
            time.sleep(wait)
        return wait
    
    # === LIFE CONTEXT METHODS ===
    
    def add_life_context(self, content: str, pillar: str, category: str = "goal",
                        auto_create_goal: bool = False) -> dict:
        """Add verified life context from user.
        
        If auto_create_goal=True, also creates a goal from the context.
        """
        ctx = self.life_context.add_context(content, pillar, category)
        
        # Optionally create goal from context
        if auto_create_goal:
            goal = self.life_context.add_goal(
                title=content[:100],  # Truncate for title
                description=content,
                pillar=pillar
            )
            return {
                "id": ctx.id,
                "content": ctx.content,
                "verified": ctx.verified,
                "goal_id": goal.id
            }
        
        return {"id": ctx.id, "content": ctx.content, "verified": ctx.verified}
    
    def update_goal_from_context(self, context_id: str, progress: float) -> bool:
        """Update goal progress and learn from outcome."""
        # Find goal by context (they share content)
        ctx = next((c for c in self.life_context.contexts if c.id == context_id), None)
        if not ctx:
            return False
        
        # Find matching goal
        goal = next((g for g in self.life_context.goals if g.pillar == ctx.pillar), None)
        if goal:
            result = self.life_context.update_goal_progress(goal.id, progress)
            
            # If completed, update capabilities
            if progress >= 100:
                self.life_context.add_capability("nexus", f"completed_goal_{ctx.pillar}")
            
            return result
        
        return False
    
    def get_pillar_status(self, pillar: str) -> dict:
        """Get status of a specific pillar."""
        return {
            'pillar': pillar,
            'contexts': len(self.life_context.get_contexts_by_pillar(pillar)),
            'goals': len(self.life_context.get_goals_by_pillar(pillar))
        }
    
    def get_life_status(self) -> dict:
        """Get full life achievement status."""
        return self.life_context.get_status()
    
    def add_capability(self, agent: str, capability: str) -> dict:
        """Add capability to an agent."""
        self.life_context.add_capability(agent, capability)
        return {"agent": agent, "capability": capability}
    
    def get_capabilities(self, agent: str) -> list[str]:
        """Get capabilities for an agent."""
        return self.life_context.get_capabilities(agent)
    
    def propose_capability_vote(self, capability: str, proposed_by: str) -> str:
        """Propose capability for consensus voting."""
        return self.life_context.propose_capability(capability, proposed_by)
    
    def vote_capability(self, vote_id: str, voter: str, approve: bool) -> bool:
        """Vote on capability proposal."""
        return self.life_context.vote_capability(vote_id, voter, approve)
    
    def can_agent_handle(self, agent: str, requirements: list[str]) -> dict:
        """Check if agent can handle task."""
        can_do, missing = self.life_context.can_handle_task(agent, requirements)
        return {"can_handle": can_do, "missing": missing}
    
    # === MONITORING METHODS ===
    
    def get_status(self) -> dict[str, Any]:
        """Get agent status."""
        uptime = time.time() - self.start_time
        total = self.tasks_completed + self.tasks_failed
        
        return {
            'running': self.running,
            'paused': self._paused,
            'uptime_seconds': uptime,
            'tasks_discovered': self.tasks_discovered,
            'tasks_completed': self.tasks_completed,
            'tasks_failed': self.tasks_failed,
            'success_rate': self.tasks_completed / total if total > 0 else 0,
            'scanner': self.scanner.get_scan_stats(),
            'executor': self.executor.get_execution_stats(),
            'learning': self.learner.get_learned_stats(),
        }
    
    def get_current_activity(self) -> dict[str, Any]:
        """Get what the agent is currently doing."""
        state = 'idle'
        current_task = None
        
        if self.running:
            if self._paused:
                state = 'paused'
            elif self.loop and self.loop.task_history:
                last = self.loop.task_history[-1]
                if last.get('start_time', 0) > time.time() - 10:
                    state = 'processing'
                    current_task = last.get('description', 'unknown')[:50]
                else:
                    state = 'ready'
        
        return {
            'state': state,
            'current_task': current_task,
            'pending_tasks': len(self.loop.get_active_tasks()) if self.loop else 0,
            'loop_state': str(self.loop.state) if self.loop else 'unknown',
            'uptime': time.time() - self.start_time,
        }
    
    def get_audit_log(self, limit: int = 100) -> list[dict]:
        """Get audit log entries."""
        entries = self._audit_log[-limit:]
        return [{'timestamp': e.timestamp, 'action': e.action, 'details': e.details, 'user': e.user} for e in entries]
    
    def ask(self, question: str) -> str:
        """Answer questions about the agent."""
        q = question.lower()
        
        if 'status' in q or 'what are you' in q:
            s = self.get_status()
            return f"Status: {'running' if s['running'] else 'stopped'}. " \
                   f"Completed: {s['tasks_completed']}, Failed: {s['tasks_failed']}. " \
                   f"Success rate: {s['success_rate']*100:.0f}%"
        
        if 'doing' in q or 'working on' in q:
            a = self.get_current_activity()
            return f"State: {a['state']}. " + (f"Task: {a['current_task']}" if a['current_task'] else "Idle")
        
        if 'help' in q or 'what can' in q:
            return "Commands: start/stop, pause/resume, inject_task(), approve/reject, " \
                   "get_status(), get_current_activity(), get_audit_log(), ask()"
        
        a = self.get_current_activity()
        return f"I'm your autonomous agent. State: {a['state']}"
    
    # === INTERNAL METHODS ===
    
    def _main_loop(self) -> None:
        """Main agent loop."""
        while self.running:
            try:
                if not self._paused:
                    discovered = self.scanner.scan()
                    if discovered:
                        self.tasks_discovered += len(discovered)
                        for task in discovered[:3]:
                            if not self._paused:
                                self._process_discovered_task(task)
                
                time.sleep(60)
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                time.sleep(30)
    
    def _process_discovered_task(self, task: DiscoveredTask) -> None:
        """Process a discovered task."""
        is_valid, violations = self.security.validate_input(task.description)
        if not is_valid:
            logger.warning(f"Task blocked: {violations}")
            return
        
        context = {'task_id': f"discovered-{time.time()}", 'source': task.source, 'priority': task.priority}
        result = self.loop.process_task(task.description, context)
        
        if result.get('success'):
            self.tasks_completed += 1
            self.learner.learn_from_task(task.description, result.get('decision', 'unknown'), True, 0, [])
        else:
            self.tasks_failed += 1
            if self.tasks_failed >= self.config.evolution_threshold:
                self._trigger_evolution(task.description, result.get('error'))
    
    def _delegate_task(self, description: str, priority: str, context: dict) -> dict:
        """Delegate task."""
        is_valid, violations = self.security.validate_input(description)
        if not is_valid:
            return {'success': False, 'error': 'Security violation', 'violations': violations}
        
        result = self.executor.execute(description)
        if result.success:
            return {'success': True, 'output': result.stdout, 'duration': result.duration_seconds}
        
        if self.task_callback:
            return self.task_callback(description, context)
        
        return {'success': False, 'error': result.error or 'Could not execute'}
    
    def _handle_result(self, result: dict) -> None:
        """Handle task result."""
        if result.get('success'):
            self.tasks_completed += 1
        else:
            self.tasks_failed += 1
    
    def _handle_security_violation(self, violations: list) -> None:
        """Handle security violations."""
        for v in violations:
            logger.warning(f"SECURITY: {v}")
    
    def _trigger_evolution(self, task: str, error: str) -> None:
        """Trigger evolution."""
        self._audit_log.append(AuditEntry(time.time(), 'evolution', f"Attempting fix for: {task[:30]}", 'system'))
        result = self.evolution.attempt_fix(task_description=task, error=error)
        self.tasks_failed = 0
        logger.info(f"Evolution fix result: {result}")
    
    def _save_state(self) -> bool:
        """Save agent state."""
        state = PersistedState()
        state.task_history = self.loop.task_history[-100:] if self.loop else []
        state.learned_patterns = self.learner.get_learned_stats().get('patterns', {})
        state.previous_state = self.previous_state
        
        # Save goals
        if hasattr(self, 'goals') and self.goals:
            from .goals import GoalManager
            if isinstance(self.goals, GoalManager):
                state.goals = []
                for g in self.goals.goals:
                    # Handle both Enum and string types
                    status_val = g.status.value if hasattr(g.status, 'value') else str(g.status)
                    priority_val = g.priority.value if hasattr(g.priority, 'value') else str(g.priority)
                    state.goals.append({
                        'id': g.id,
                        'title': g.title,
                        'status': status_val,
                        'priority': priority_val,
                        'progress': g.progress,
                    })
        
        return self.persistence.save(state)
    
    def execute_command(self, command: str) -> dict[str, Any]:
        """Execute a command directly."""
        result = self.executor.execute(command)
        return {'success': result.success, 'stdout': result.stdout, 'stderr': result.stderr, 'exit_code': result.exit_code, 'duration': result.duration_seconds}
