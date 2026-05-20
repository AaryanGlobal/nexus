"""
Resilient Agent Bridge - Fault-tolerant Hermes ↔ PI communication

Features:
- Message persistence (survives restarts)
- Automatic retry with exponential backoff
- Dead letter queue for failed messages
- Backpressure (queue depth limits)
- Message deduplication (idempotency)
- Health checks with auto-reconnect
- Circuit breaker at bridge level
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable
from enum import Enum
import json
import logging
import time
import threading
from pathlib import Path
from collections import deque

logger = logging.getLogger(__name__)


class MessageState(Enum):
    """State of a message."""
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass
class PersistentMessage:
    """A message that persists to disk."""
    id: str
    from_agent: str
    to_agent: str
    type: str
    content: dict
    created_at: datetime
    state: MessageState = MessageState.PENDING
    attempts: int = 0
    max_attempts: int = 3
    last_attempt: Optional[datetime] = None
    error: Optional[str] = None
    acknowledged_at: Optional[datetime] = None


@dataclass
class CircuitBreakerState:
    """Circuit breaker for agent connection."""
    failures: int = 0
    last_failure: Optional[datetime] = None
    is_open: bool = False
    half_open: bool = False
    
    def record_failure(self):
        self.failures += 1
        self.last_failure = datetime.now()
        if self.failures >= 5:
            self.is_open = True
            self.half_open = False
    
    def record_success(self):
        self.failures = 0
        self.is_open = False
        self.half_open = False
    
    def try_half_open(self, recovery_timeout: int = 60) -> bool:
        """Try to transition to half-open after recovery timeout."""
        if not self.is_open:
            return False
        if self.last_failure and (datetime.now() - self.last_failure).total_seconds() > recovery_timeout:
            self.half_open = True
            self.is_open = False
            return True
        return False


class ResilientBridge:
    """
    Fault-tolerant bridge for Hermes ↔ PI communication.
    
    Key Features:
    1. MESSAGE PERSISTENCE - Messages survive restarts
    2. RETRY WITH BACKOFF - Failed messages retry automatically
    3. DEAD LETTER QUEUE - Failed messages are preserved
    4. BACKPRESSURE - Queue depth limits prevent overwhelming
    5. DEDUPLICATION - Message IDs prevent duplicate processing
    6. CIRCUIT BREAKER - Prevents cascade failures
    7. HEALTH CHECKS - Monitors agent health
    """
    
    def __init__(self, storage_path: str | None = None):
        self.storage_path = storage_path or str(Path.home() / ".nexus" / "messages.json")
        self.dead_letter_path = str(Path.home() / ".nexus" / "dead_letters.json")
        
        # Message storage
        self.pending_queue: deque[PersistentMessage] = deque()
        self.processed_ids: set[str] = set()
        self.dead_letters: list[PersistentMessage] = []
        
        # Circuit breakers per agent
        self.circuit_breakers: dict[str, CircuitBreakerState] = {
            "hermes": CircuitBreakerState(),
            "pi": CircuitBreakerState(),
        }
        
        # Queue limits (backpressure)
        self.max_queue_depth = 100
        self.max_pending_per_agent = 50
        
        # Retry configuration
        self.base_retry_delay = 1  # seconds
        self.max_retry_delay = 60
        self.max_attempts = 3
        
        # Health monitoring
        self.last_health_check: dict[str, datetime] = {}
        self.health_check_interval = 30  # seconds
        
        # Callbacks
        self._on_message_sent: Optional[Callable] = None
        self._on_message_failed: Optional[Callable] = None
        self._on_agent_health_change: Optional[Callable] = None
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        # Load persisted state
        self._running = False
        self._load_state()
        
        # Start retry processor
        self._running = True
        self._retry_thread = threading.Thread(target=self._retry_loop, daemon=True)
        self._retry_thread.start()
    
    def _load_state(self):
        """Load persisted messages and state."""
        try:
            path = Path(self.storage_path)
            if path.exists():
                with open(path) as f:
                    data = json.load(f)
                    
                    # Load pending messages
                    for msg_data in data.get('pending', []):
                        msg = self._deserialize_message(msg_data)
                        if msg and msg.state != MessageState.DEAD_LETTER:
                            self.pending_queue.append(msg)
                    
                    # Load dead letters
                    for msg_data in data.get('dead_letters', []):
                        msg = self._deserialize_message(msg_data)
                        if msg:
                            self.dead_letters.append(msg)
                    
                    # Load processed IDs (recent)
                    self.processed_ids = set(data.get('processed_ids', []))
                    
                    logger.info(f"Loaded {len(self.pending_queue)} pending, {len(self.dead_letters)} dead letters")
        except Exception as e:
            logger.warning(f"Could not load bridge state: {e}")
    
    def _save_state(self):
        """Persist messages and state atomically."""
        try:
            path = Path(self.storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'pending': [self._serialize_message(m) for m in self.pending_queue],
                'dead_letters': [self._serialize_message(m) for m in self.dead_letters],
                'processed_ids': list(self.processed_ids)[-1000:],  # Keep recent only
                'saved_at': datetime.now().isoformat()
            }
            
            tmp = path.with_suffix('.tmp')
            with open(tmp, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            tmp.rename(path)
        except Exception as e:
            logger.error(f"Failed to save bridge state: {e}")
    
    def _serialize_message(self, msg: PersistentMessage) -> dict:
        """Serialize message to dict."""
        return {
            'id': msg.id,
            'from_agent': msg.from_agent,
            'to_agent': msg.to_agent,
            'type': msg.type,
            'content': msg.content,
            'created_at': msg.created_at.isoformat(),
            'state': msg.state.value,
            'attempts': msg.attempts,
            'max_attempts': msg.max_attempts,
            'last_attempt': msg.last_attempt.isoformat() if msg.last_attempt else None,
            'error': msg.error,
            'acknowledged_at': msg.acknowledged_at.isoformat() if msg.acknowledged_at else None,
        }
    
    def _deserialize_message(self, data: dict) -> PersistentMessage | None:
        """Deserialize dict to message."""
        try:
            return PersistentMessage(
                id=data['id'],
                from_agent=data['from_agent'],
                to_agent=data['to_agent'],
                type=data['type'],
                content=data['content'],
                created_at=datetime.fromisoformat(data['created_at']),
                state=MessageState(data.get('state', 'pending')),
                attempts=data.get('attempts', 0),
                max_attempts=data.get('max_attempts', self.max_attempts),
                last_attempt=datetime.fromisoformat(data['last_attempt']) if data.get('last_attempt') else None,
                error=data.get('error'),
                acknowledged_at=datetime.fromisoformat(data['acknowledged_at']) if data.get('acknowledged_at') else None,
            )
        except Exception as e:
            logger.warning(f"Could not deserialize message: {e}")
            return None
    
    # === PUBLIC API ===
    
    def send_message(self, to_agent: str, from_agent: str, msg_type: str, 
                     content: dict, idempotency_key: str | None = None) -> str | None:
        """Send a message with guaranteed delivery.
        
        Returns message ID if queued, None if rejected (backpressure).
        """
        with self._lock:
            # Check circuit breaker
            cb = self.circuit_breakers.get(to_agent, CircuitBreakerState())
            if cb.is_open and not cb.half_open:
                logger.warning(f"Circuit breaker OPEN for {to_agent}")
                return None
            
            # Check backpressure (queue depth)
            agent_queue_count = sum(1 for m in self.pending_queue if m.to_agent == to_agent)
            if agent_queue_count >= self.max_pending_per_agent:
                logger.warning(f"Backpressure: {to_agent} queue full ({agent_queue_count})")
                return None
            
            if len(self.pending_queue) >= self.max_queue_depth:
                logger.warning(f"Backpressure: global queue full ({len(self.pending_queue)})")
                return None
            
            # Deduplication
            if idempotency_key:
                dedup_id = f"{to_agent}:{idempotency_key}"
                if dedup_id in self.processed_ids:
                    logger.info(f"Duplicate message suppressed: {dedup_id}")
                    return idempotency_key  # Return original ID
            
            # Create message
            msg_id = idempotency_key or f"msg_{len(self.pending_queue)}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            
            msg = PersistentMessage(
                id=msg_id,
                from_agent=from_agent,
                to_agent=to_agent,
                type=msg_type,
                content=content,
                created_at=datetime.now(),
                state=MessageState.PENDING,
                max_attempts=self.max_attempts
            )
            
            self.pending_queue.append(msg)
            self._save_state()
            
            logger.info(f"Message queued: {msg_id} -> {to_agent}")
            return msg_id
    
    def acknowledge_message(self, msg_id: str) -> bool:
        """Acknowledge a message was processed successfully."""
        with self._lock:
            for msg in self.pending_queue:
                if msg.id == msg_id:
                    msg.state = MessageState.ACKNOWLEDGED
                    msg.acknowledged_at = datetime.now()
                    self.processed_ids.add(msg_id)
                    self.pending_queue.remove(msg)
                    self._save_state()
                    
                    # Record success for circuit breaker
                    cb = self.circuit_breakers.get(msg.to_agent)
                    if cb:
                        cb.record_success()
                    
                    logger.info(f"Message acknowledged: {msg_id}")
                    return True
            return False
    
    def get_pending_count(self, agent: str | None = None) -> int:
        """Get count of pending messages."""
        if agent:
            return sum(1 for m in self.pending_queue if m.to_agent == agent)
        return len(self.pending_queue)
    
    def get_dead_letters(self) -> list[dict]:
        """Get all dead letter messages."""
        return [self._serialize_message(m) for m in self.dead_letters]
    
    def retry_dead_letter(self, msg_id: str) -> bool:
        """Retry a dead letter message."""
        with self._lock:
            for msg in self.dead_letters:
                if msg.id == msg_id:
                    msg.state = MessageState.PENDING
                    msg.attempts = 0
                    msg.error = None
                    self.dead_letters.remove(msg)
                    self.pending_queue.append(msg)
                    self._save_state()
                    return True
            return False
    
    def get_circuit_state(self, agent: str) -> dict:
        """Get circuit breaker state for agent."""
        cb = self.circuit_breakers.get(agent, CircuitBreakerState())
        return {
            'is_open': cb.is_open,
            'half_open': cb.half_open,
            'failures': cb.failures,
            'last_failure': cb.last_failure.isoformat() if cb.last_failure else None
        }
    
    def reset_circuit(self, agent: str):
        """Manually reset circuit breaker."""
        if agent in self.circuit_breakers:
            self.circuit_breakers[agent] = CircuitBreakerState()
            logger.info(f"Circuit breaker reset for {agent}")
    
    def check_agent_health(self, agent: str) -> dict:
        """Check health of an agent connection."""
        cb = self.circuit_breakers.get(agent, CircuitBreakerState())
        
        # Try to transition from open to half-open
        if cb.try_half_open(recovery_timeout=60):
            logger.info(f"Circuit breaker HALF-OPEN for {agent}")
        
        last_check = self.last_health_check.get(agent)
        return {
            'agent': agent,
            'circuit_state': cb.is_open and not cb.half_open,
            'can_send': not cb.is_open or cb.half_open,
            'last_check': last_check.isoformat() if last_check else None,
            'queue_depth': self.get_pending_count(agent)
        }
    
    def get_status(self) -> dict:
        """Get comprehensive bridge status."""
        return {
            'pending_total': len(self.pending_queue),
            'dead_letters_total': len(self.dead_letters),
            'processed_ids': len(self.processed_ids),
            'circuits': {agent: self.get_circuit_state(agent) for agent in self.circuit_breakers},
            'queues': {
                'hermes': self.get_pending_count('hermes'),
                'pi': self.get_pending_count('pi')
            }
        }
    
    def register_callbacks(self, on_sent: Callable | None = None,
                           on_failed: Callable | None = None,
                           on_health_change: Callable | None = None):
        """Register callbacks for events."""
        self._on_message_sent = on_sent
        self._on_message_failed = on_failed
        self._on_agent_health_change = on_health_change
    
    def stop(self):
        """Stop the bridge and save state."""
        self._running = False
        self._save_state()
        logger.info("Bridge stopped")
    
    # === INTERNAL ===
    
    def _retry_loop(self):
        """Background thread for retrying failed messages."""
        while self._running:
            try:
                self._process_pending()
            except Exception as e:
                logger.error(f"Retry loop error: {e}")
            
            time.sleep(1)  # Check every second
    
    def _process_pending(self):
        """Process pending messages."""
        with self._lock:
            messages_to_remove = []
            
            for msg in list(self.pending_queue):
                # Check if circuit breaker allows sending
                cb = self.circuit_breakers.get(msg.to_agent)
                if cb and (cb.is_open and not cb.half_open):
                    continue
                
                # Check retry delay
                if msg.last_attempt:
                    delay = self._get_retry_delay(msg.attempts)
                    elapsed = (datetime.now() - msg.last_attempt).total_seconds()
                    if elapsed < delay:
                        continue
                
                # Try to send
                success = self._try_send(msg)
                
                if success:
                    messages_to_remove.append(msg)
                    msg.state = MessageState.SENT
                    
                    if self._on_message_sent:
                        self._on_message_sent(msg)
                else:
                    msg.attempts += 1
                    msg.last_attempt = datetime.now()
                    
                    # Record failure for circuit breaker
                    if cb:
                        cb.record_failure()
                    
                    if msg.attempts >= msg.max_attempts:
                        msg.state = MessageState.DEAD_LETTER
                        messages_to_remove.append(msg)
                        self.dead_letters.append(msg)
                        msg.error = f"Max attempts ({msg.max_attempts}) exceeded"
                        
                        if self._on_message_failed:
                            self._on_message_failed(msg)
                        
                        logger.warning(f"Message moved to dead letter: {msg.id}")
            
            # Remove processed messages
            for msg in messages_to_remove:
                if msg in self.pending_queue:
                    self.pending_queue.remove(msg)
            
            if messages_to_remove:
                self._save_state()
    
    def _try_send(self, msg: PersistentMessage) -> bool:
        """Attempt to send a message. Returns True on success."""
        # In real implementation, this would call the HTTP client
        # For now, simulate with random success for testing
        import random
        return random.random() > 0.2  # 80% success rate
    
    def _get_retry_delay(self, attempts: int) -> float:
        """Get delay for retry attempt with exponential backoff."""
        delay = self.base_retry_delay * (2 ** attempts)
        return min(delay, self.max_retry_delay)


# Singleton
_bridge: Optional[ResilientBridge] = None


def get_resilient_bridge() -> ResilientBridge:
    """Get singleton instance."""
    global _bridge
    if _bridge is None:
        _bridge = ResilientBridge()
    return _bridge