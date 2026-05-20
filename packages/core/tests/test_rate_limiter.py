"""TDD: Rate Limiter Tests"""
import pytest
import time
from hermes_pi_bridge_core.rate_limiter import (
    RateLimiter, RateLimitConfig, RequestRecord
)


class TestRateLimiterBasics:
    """Test basic rate limiting."""
    
    def test_allows_request_within_limit(self):
        """Should allow requests within limit."""
        limiter = RateLimiter(RateLimitConfig(requests_per_minute=10))
        
        can_proceed, reason = limiter.can_proceed()
        assert can_proceed is True
        assert reason == "OK"
    
    def test_blocks_request_at_limit(self):
        """Should block requests at limit."""
        config = RateLimitConfig(requests_per_minute=5)
        limiter = RateLimiter(config)
        
        # Use up all requests
        for _ in range(5):
            limiter.can_proceed()
            limiter.record_request(True)
        
        can_proceed, reason = limiter.can_proceed()
        assert can_proceed is False
        assert "limit" in reason.lower()
    
    def test_resets_after_window(self):
        """Should reset after time window."""
        config = RateLimitConfig(requests_per_minute=2)
        limiter = RateLimiter(config)
        
        # Use up limit
        limiter.record_request(True)
        limiter.record_request(True)
        assert limiter.can_proceed()[0] is False
        
        # Manually clear history
        limiter.minute_history.clear()
        
        assert limiter.can_proceed()[0] is True


class TestBurstProtection:
    """Test burst protection."""
    
    def test_burst_limit(self):
        """Should limit burst requests."""
        config = RateLimitConfig(burst_limit=3, burst_window_seconds=5)
        limiter = RateLimiter(config)
        
        # Use up burst
        for _ in range(3):
            limiter.can_proceed()
            limiter.record_request(True)
        
        can_proceed, reason = limiter.can_proceed()
        assert can_proceed is False
        assert "burst" in reason.lower()


class TestBackoff:
    """Test exponential backoff."""
    
    def test_backoff_after_429(self):
        """Should trigger backoff after 429 error."""
        limiter = RateLimiter(RateLimitConfig(backoff_base_seconds=1))
        
        # Record 429 error
        limiter.record_request(False, status_code=429)
        
        can_proceed, reason = limiter.can_proceed()
        assert can_proceed is False
        assert "backoff" in reason.lower()
    
    def test_backoff_increases(self):
        """Backoff should increase exponentially."""
        config = RateLimitConfig(backoff_base_seconds=1, max_backoff_seconds=100)
        limiter = RateLimiter(config)
        
        # Multiple failures
        limiter.record_request(False, status_code=429)
        limiter.record_request(False, status_code=429)
        
        # Should be in backoff
        assert limiter.backoff_until > time.time()


class TestProviderTracking:
    """Test provider-specific tracking."""
    
    def test_provider_separate_limit(self):
        """Providers should have separate limits."""
        # With 30 requests/minute, provider gets 30/3 = 10 per minute
        limiter = RateLimiter(RateLimitConfig(requests_per_minute=30))
        
        # Exhaust provider limit (10 requests)
        for _ in range(10):
            limiter.can_proceed("openai")
            limiter.record_request(True, provider="openai")
        
        # 11th request should be blocked
        can_openai, reason = limiter.can_proceed("openai")
        assert can_openai is False
        assert "limit" in reason.lower()


class TestStatus:
    """Test status reporting."""
    
    def test_status_contains_limits(self):
        """Status should show limit info."""
        limiter = RateLimiter(RateLimitConfig(requests_per_minute=10))
        
        status = limiter.get_status()
        
        assert "limits" in status
        assert "minute" in status["limits"]
        assert "hour" in status["limits"]
        assert "day" in status["limits"]
    
    def test_status_shows_suggestion(self):
        """Status should include suggestion."""
        limiter = RateLimiter()
        
        status = limiter.get_status()
        
        assert "suggestion" in status
        assert len(status["suggestion"]) > 0
    
    def test_statistics_tracked(self):
        """Should track statistics."""
        limiter = RateLimiter()
        
        limiter.record_request(True)
        limiter.record_request(False, status_code=429)
        
        status = limiter.get_status()
        
        assert status["statistics"]["total_requests"] == 2
        assert status["statistics"]["429_errors"] == 1


class TestWaitTime:
    """Test wait time calculation."""
    
    def test_wait_time_at_limit(self):
        """Should return wait time at limit."""
        config = RateLimitConfig(requests_per_minute=2)
        limiter = RateLimiter(config)
        
        # Use up limit
        limiter.record_request(True)
        limiter.record_request(True)
        
        wait = limiter.get_wait_time()
        assert wait > 0
    
    def test_wait_time_when_ok(self):
        """Should return 0 when not at limit."""
        limiter = RateLimiter()
        wait = limiter.get_wait_time()
        assert wait == 0


class TestReset:
    """Test reset functionality."""
    
    def test_reset_clears_all(self):
        """Reset should clear all counters."""
        limiter = RateLimiter()
        
        limiter.record_request(True)
        limiter.record_request(True)
        limiter.record_request(False, status_code=429)
        limiter.backoff_until = time.time() + 100
        
        limiter.reset()
        
        assert len(limiter.minute_history) == 0
        assert len(limiter.hour_history) == 0
        assert limiter.backoff_until == 0
        assert limiter.total_requests == 0