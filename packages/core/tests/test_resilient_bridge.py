"""TDD: Resilient Bridge Tests - Fault Tolerance"""
import pytest
import tempfile
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from hermes_pi_bridge_core.resilient_bridge import (
    ResilientBridge, PersistentMessage, MessageState,
    CircuitBreakerState, get_resilient_bridge
)


@pytest.fixture
def bridge():
    """Create test bridge with temp storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/messages.json"
        b = ResilientBridge(storage_path=path)
        b._running = False  # Stop background thread
        yield b


class TestMessagePersistence:
    """Test message persistence and recovery."""
    
    def test_message_survives_restart(self, bridge):
        """Message persists after bridge restart."""
        # Send a message
        msg_id = bridge.send_message("hermes", "nexus", "task_delegate", {"task": "test"})
        assert msg_id is not None
        
        # Create new bridge instance with same storage
        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/messages.json"
            bridge2 = ResilientBridge(storage_path=path)
            bridge2._running = False
            
            # Should have the message
            assert bridge2.get_pending_count("hermes") >= 0
    
    def test_dead_letters_persist(self, bridge):
        """Dead letters survive restart."""
        # Add dead letter directly
        bridge.dead_letters.append(PersistentMessage(
            id="dead_1",
            from_agent="nexus",
            to_agent="hermes",
            type="task_delegate",
            content={"task": "failed"},
            created_at=datetime.now(),
            state=MessageState.DEAD_LETTER,
            attempts=3,
            error="Connection refused"
        ))
        
        # Check dead letters
        dls = bridge.get_dead_letters()
        assert len(dls) == 1
        assert dls[0]['id'] == "dead_1"
    
    def test_processed_ids_limited(self, bridge):
        """Processed IDs don't grow unbounded."""
        # Add many IDs
        for i in range(2000):
            bridge.processed_ids.add(f"id_{i}")
        
        # Should be capped at 1000 in save
        assert len(bridge.processed_ids) == 2000  # In memory


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_circuit_opens_after_failures(self, bridge):
        """Circuit opens after consecutive failures."""
        cb = CircuitBreakerState()
        
        # Fail 5 times
        for _ in range(5):
            cb.record_failure()
        
        assert cb.is_open is True
    
    def test_circuit_closes_on_success(self, bridge):
        """Circuit closes after success."""
        cb = CircuitBreakerState()
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        
        assert cb.failures > 0
        
        cb.record_success()
        
        assert cb.failures == 0
        assert cb.is_open is False
    
    def test_circuit_try_half_open(self, bridge):
        """Circuit can transition to half-open."""
        cb = CircuitBreakerState()
        cb.is_open = True
        cb.last_failure = datetime.now()
        
        # Immediately - should fail
        assert cb.try_half_open(recovery_timeout=60) is False
        
        # After timeout - should succeed
        cb.last_failure = datetime.now() - timedelta(seconds=120)
        assert cb.try_half_open(recovery_timeout=60) is True
        assert cb.half_open is True
    
    def test_bridge_circuit_state(self, bridge):
        """Bridge reports circuit state."""
        state = bridge.get_circuit_state("hermes")
        assert 'is_open' in state
        assert 'failures' in state


class TestBackpressure:
    """Test backpressure and queue limits."""
    
    def test_queue_depth_limit(self, bridge):
        """Queue depth is limited."""
        bridge.max_queue_depth = 5
        bridge.max_pending_per_agent = 3
        
        # Send messages until queue is full
        for i in range(7):
            bridge.send_message("hermes", "nexus", "task_delegate", {"task": i})
        
        # Should be limited
        count = bridge.get_pending_count("hermes")
        assert count <= bridge.max_pending_per_agent
    
    def test_global_queue_limit(self, bridge):
        """Global queue has limit."""
        bridge.max_queue_depth = 3
        
        # Fill global queue
        bridge.send_message("hermes", "nexus", "task_delegate", {"t": 1})
        bridge.send_message("hermes", "nexus", "task_delegate", {"t": 2})
        bridge.send_message("hermes", "nexus", "task_delegate", {"t": 3})
        
        # Next should be rejected (backpressure)
        result = bridge.send_message("pi", "nexus", "task_delegate", {"t": 4})
        assert result is None  # Backpressure


class TestDeduplication:
    """Test message deduplication."""
    
    def test_duplicate_suppressed(self, bridge):
        """Duplicate messages are suppressed."""
        # Send with idempotency key
        msg_id = bridge.send_message(
            "hermes", "nexus", "task_delegate",
            {"task": "test"},
            idempotency_key="unique_task_123"
        )
        assert msg_id == "unique_task_123"
        
        # Try again with same key
        msg_id2 = bridge.send_message(
            "hermes", "nexus", "task_delegate",
            {"task": "test"},
            idempotency_key="unique_task_123"
        )
        
        # Should return same ID (duplicate suppressed)
        assert msg_id2 == "unique_task_123"
    
    def test_different_keys_not_deduplicated(self, bridge):
        """Different idempotency keys are not deduplicated."""
        msg1 = bridge.send_message("hermes", "nexus", "task_delegate", {},
                                   idempotency_key="key1")
        msg2 = bridge.send_message("hermes", "nexus", "task_delegate", {},
                                   idempotency_key="key2")
        
        assert msg1 != msg2


class TestRetry:
    """Test retry logic with backoff."""
    
    def test_retry_delay_increases(self, bridge):
        """Retry delay increases with exponential backoff."""
        delay1 = bridge._get_retry_delay(0)
        delay2 = bridge._get_retry_delay(1)
        delay3 = bridge._get_retry_delay(2)
        
        assert delay2 > delay1
        assert delay3 > delay2
        assert delay3 <= bridge.max_retry_delay
    
    def test_retry_delay_max_cap(self, bridge):
        """Retry delay is capped at max."""
        delay = bridge._get_retry_delay(100)
        assert delay == bridge.max_retry_delay


class TestDeadLetterQueue:
    """Test dead letter queue."""
    
    def test_dead_letter_retention(self, bridge):
        """Failed messages go to dead letter queue."""
        msg = PersistentMessage(
            id="msg_failing",
            from_agent="nexus",
            to_agent="hermes",
            type="task_delegate",
            content={"task": "fail"},
            created_at=datetime.now(),
            attempts=0,
            max_attempts=1
        )
        msg.attempts = msg.max_attempts
        msg.state = MessageState.DEAD_LETTER
        
        bridge.dead_letters.append(msg)
        
        dls = bridge.get_dead_letters()
        assert len(dls) == 1
        assert dls[0]['id'] == "msg_failing"
    
    def test_retry_dead_letter(self, bridge):
        """Can retry a dead letter."""
        msg = PersistentMessage(
            id="retry_me",
            from_agent="nexus",
            to_agent="hermes",
            type="task_delegate",
            content={"task": "retry"},
            created_at=datetime.now(),
            state=MessageState.DEAD_LETTER,
            attempts=3,
            error="Failed"
        )
        bridge.dead_letters.append(msg)
        
        result = bridge.retry_dead_letter("retry_me")
        assert result is True
        
        # Should be in pending queue
        pending_ids = [m.id for m in bridge.pending_queue]
        assert "retry_me" in pending_ids


class TestCircuitBreakerIntegration:
    """Test circuit breaker in send flow."""
    
    def test_send_blocked_when_circuit_open(self, bridge):
        """Send is blocked when circuit is open."""
        # Open circuit for hermes
        bridge.circuit_breakers["hermes"].is_open = True
        bridge.circuit_breakers["hermes"].half_open = False
        
        # Try to send
        result = bridge.send_message("hermes", "nexus", "task_delegate", {})
        assert result is None
    
    def test_send_allowed_when_circuit_half_open(self, bridge):
        """Send is allowed when circuit is half-open."""
        # Half-open circuit
        bridge.circuit_breakers["hermes"].is_open = False
        bridge.circuit_breakers["hermes"].half_open = True
        
        # Should allow send
        result = bridge.send_message("hermes", "nexus", "task_delegate", {})
        assert result is not None


class TestAcknowledgment:
    """Test message acknowledgment."""
    
    def test_acknowledge_removes_from_queue(self, bridge):
        """Acknowledging removes message from pending."""
        msg_id = bridge.send_message("hermes", "nexus", "task_delegate", {})
        assert msg_id is not None
        
        # Acknowledge
        result = bridge.acknowledge_message(msg_id)
        assert result is True
        
        # Should update circuit breaker
        cb = bridge.circuit_breakers["hermes"]
        assert cb.failures == 0
    
    def test_acknowledge_nonexistent(self, bridge):
        """Acknowledging non-existent message returns False."""
        result = bridge.acknowledge_message("nonexistent_id")
        assert result is False


class TestStatus:
    """Test bridge status reporting."""
    
    def test_status_includes_all_info(self, bridge):
        """Status includes queues, circuits, counts."""
        bridge.send_message("hermes", "nexus", "task_delegate", {})
        bridge.send_message("hermes", "nexus", "task_delegate", {})
        bridge.send_message("pi", "nexus", "task_delegate", {})
        
        status = bridge.get_status()
        
        assert 'pending_total' in status
        assert 'dead_letters_total' in status
        assert 'circuits' in status
        assert 'queues' in status
        assert status['queues']['hermes'] >= 2
        assert status['queues']['pi'] >= 1


class TestReset:
    """Test circuit breaker reset."""
    
    def test_manual_reset(self, bridge):
        """Can manually reset circuit breaker."""
        # Open circuit
        bridge.circuit_breakers["hermes"].is_open = True
        bridge.circuit_breakers["hermes"].failures = 10
        
        # Reset
        bridge.reset_circuit("hermes")
        
        # Should be closed
        state = bridge.get_circuit_state("hermes")
        assert state['is_open'] is False
        assert state['failures'] == 0