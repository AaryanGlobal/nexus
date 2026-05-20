"""
Smart Rate Limiter - Prevents API rate limits
Tracks requests and paces them to avoid provider blocks
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from collections import deque
import time


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 30      # Max requests per minute
    requests_per_hour: int = 1000      # Max requests per hour
    requests_per_day: int = 10000      # Max requests per day
    burst_limit: int = 10              # Max burst requests
    burst_window_seconds: int = 5      # Burst window
    backoff_base_seconds: int = 60     # Base backoff time
    max_backoff_seconds: int = 3600    # Max backoff time


@dataclass 
class RequestRecord:
    """Record of a single request."""
    timestamp: float
    provider: str
    endpoint: str
    success: bool
    status_code: Optional[int] = None


class RateLimiter:
    """
    Smart rate limiter that tracks requests and paces them.
    
    Features:
    - Token bucket algorithm for smooth pacing
    - Per-minute, per-hour, per-day limits
    - Burst protection
    - Exponential backoff on rate limit errors
    - Provider-specific tracking
    - Smart queuing
    """
    
    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        
        # Request history (rolling windows)
        self.minute_history: deque = deque(maxlen=self.config.requests_per_minute)
        self.hour_history: deque = deque(maxlen=self.config.requests_per_hour)
        self.day_history: deque = deque(maxlen=self.config.requests_per_day)
        self.burst_history: deque = deque(maxlen=self.config.burst_limit)
        
        # Provider-specific tracking
        self.provider_history: dict[str, deque] = {}
        
        # Backoff state
        self.backoff_until: float = 0
        self.consecutive_failures: int = 0
        
        # Queue for pending requests
        self.pending_queue: list = []
        
        # Statistics
        self.total_requests: int = 0
        self.total_429_errors: int = 0
        self.total_blocks: int = 0
    
    def can_proceed(self, provider: str = "default") -> tuple[bool, str]:
        """
        Check if a request can proceed.
        Returns (can_proceed, reason).
        """
        now = time.time()
        
        # Check backoff
        if now < self.backoff_until:
            wait = self.backoff_until - now
            return False, f"In backoff, wait {wait:.0f}s"
        
        # Check burst limit
        self._clean_burst_history()
        if len(self.burst_history) >= self.config.burst_limit:
            return False, "Burst limit reached"
        
        # Check minute limit
        self._clean_minute_history()
        if len(self.minute_history) >= self.config.requests_per_minute:
            return False, "Minute limit reached"
        
        # Check hour limit
        self._clean_hour_history()
        if len(self.hour_history) >= self.config.requests_per_hour:
            return False, "Hour limit reached"
        
        # Check day limit
        self._clean_day_history()
        if len(self.day_history) >= self.config.requests_per_day:
            return False, "Daily limit reached"
        
        # Check provider-specific limits
        if provider != "default":
            if provider not in self.provider_history:
                self.provider_history[provider] = deque(maxlen=self.config.requests_per_minute)
            
            self._clean_provider_history(provider)
            if len(self.provider_history[provider]) >= self.config.requests_per_minute // 3:
                return False, f"Provider {provider} limit reached"
        
        return True, "OK"
    
    def record_request(self, success: bool, status_code: Optional[int] = None,
                     provider: str = "default", endpoint: str = ""):
        """Record a request (successful or not)."""
        now = time.time()
        
        record = RequestRecord(
            timestamp=now,
            provider=provider,
            endpoint=endpoint,
            success=success,
            status_code=status_code
        )
        
        # Add to histories
        self.minute_history.append(now)
        self.hour_history.append(now)
        self.day_history.append(now)
        self.burst_history.append(now)
        
        if provider != "default":
            if provider not in self.provider_history:
                self.provider_history[provider] = deque(maxlen=self.config.requests_per_minute)
            self.provider_history[provider].append(now)
        
        self.total_requests += 1
        
        # Handle rate limit response (429)
        if status_code == 429:
            self.total_429_errors += 1
            self._trigger_backoff()
        elif not success:
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0
    
    def _trigger_backoff(self):
        """Trigger exponential backoff after rate limit error."""
        # Exponential backoff: base * 2^failures
        backoff = min(
            self.config.backoff_base_seconds * (2 ** min(self.consecutive_failures, 10)),
            self.config.max_backoff_seconds
        )
        self.backoff_until = time.time() + backoff
        self.consecutive_failures += 1
    
    def _clean_burst_history(self):
        """Clean burst history older than window."""
        now = time.time()
        while self.burst_history and now - self.burst_history[0] > self.config.burst_window_seconds:
            self.burst_history.popleft()
    
    def _clean_minute_history(self):
        """Clean minute history older than 1 minute."""
        now = time.time()
        while self.minute_history and now - self.minute_history[0] > 60:
            self.minute_history.popleft()
    
    def _clean_hour_history(self):
        """Clean hour history older than 1 hour."""
        now = time.time()
        while self.hour_history and now - self.hour_history[0] > 3600:
            self.hour_history.popleft()
    
    def _clean_day_history(self):
        """Clean day history older than 1 day."""
        now = time.time()
        while self.day_history and now - self.day_history[0] > 86400:
            self.day_history.popleft()
    
    def _clean_provider_history(self, provider: str):
        """Clean provider history older than 1 minute."""
        now = time.time()
        history = self.provider_history[provider]
        while history and now - history[0] > 60:
            history.popleft()
    
    def get_wait_time(self, provider: str = "default") -> float:
        """Get recommended wait time before next request."""
        now = time.time()
        
        # Check backoff
        if now < self.backoff_until:
            return self.backoff_until - now
        
        # Calculate wait for each limit
        waits = []
        
        # Minute limit
        self._clean_minute_history()
        if len(self.minute_history) >= self.config.requests_per_minute:
            oldest = self.minute_history[0]
            waits.append(60 - (now - oldest))
        
        # Hour limit
        self._clean_hour_history()
        if len(self.hour_history) >= self.config.requests_per_hour:
            oldest = self.hour_history[0]
            waits.append(3600 - (now - oldest))
        
        # Day limit
        self._clean_day_history()
        if len(self.day_history) >= self.config.requests_per_day:
            oldest = self.day_history[0]
            waits.append(86400 - (now - oldest))
        
        return max(waits) if waits else 0
    
    def get_status(self) -> dict:
        """Get comprehensive rate limit status."""
        now = time.time()
        
        return {
            "can_proceed": self.can_proceed("default")[0],
            "backoff_active": now < self.backoff_until,
            "backoff_remaining": max(0, self.backoff_until - now),
            "limits": {
                "minute": {
                    "used": len(self.minute_history),
                    "max": self.config.requests_per_minute,
                    "remaining": self.config.requests_per_minute - len(self.minute_history),
                    "pct": len(self.minute_history) / self.config.requests_per_minute
                },
                "hour": {
                    "used": len(self.hour_history),
                    "max": self.config.requests_per_hour,
                    "remaining": self.config.requests_per_hour - len(self.hour_history),
                    "pct": len(self.hour_history) / self.config.requests_per_hour
                },
                "day": {
                    "used": len(self.day_history),
                    "max": self.config.requests_per_day,
                    "remaining": self.config.requests_per_day - len(self.day_history),
                    "pct": len(self.day_history) / self.config.requests_per_day
                }
            },
            "statistics": {
                "total_requests": self.total_requests,
                "429_errors": self.total_429_errors,
                "consecutive_failures": self.consecutive_failures
            },
            "suggestion": self._get_suggestion()
        }
    
    def _get_suggestion(self) -> str:
        """Get a human-readable suggestion."""
        now = time.time()
        
        if now < self.backoff_until:
            return f"⚠️ Backoff active. Wait {self.backoff_until - now:.0f}s"
        
        if len(self.minute_history) >= self.config.requests_per_minute:
            oldest = self.minute_history[0]
            wait = 60 - (now - oldest)
            return f"⏱️ Minute limit. Wait {wait:.0f}s"
        
        if len(self.hour_history) >= self.config.requests_per_hour:
            oldest = self.hour_history[0]
            wait = 3600 - (now - oldest)
            return f"⏱️ Hour limit. Wait {wait:.0f}s"
        
        remaining = self.config.requests_per_minute - len(self.minute_history)
        return f"✅ OK. Can make ~{remaining} more requests this minute"
    
    def reset(self):
        """Reset all counters."""
        self.minute_history.clear()
        self.hour_history.clear()
        self.day_history.clear()
        self.burst_history.clear()
        self.provider_history.clear()
        self.backoff_until = 0
        self.consecutive_failures = 0
        self.total_requests = 0
        self.total_429_errors = 0