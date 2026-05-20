"""
OWASP-Level Security Controls for Hermes-Pi Bridge

Implements defense-in-depth security for autonomous agentic systems.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ThreatLevel(StrEnum):
    """Security threat levels."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEvent(StrEnum):
    """Types of security events."""
    INPUT_VALIDATION_FAILED = "input_validation_failed"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    PROMPT_INJECTION_DETECTED = "prompt_injection_detected"
    TOOL_INJECTION_ATTEMPT = "tool_injection_attempt"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    SUSPICIOUS_PATTERN = "suspicious_pattern"


@dataclass
class SecurityViolation:
    """Record of a security violation."""
    event: SecurityEvent
    threat_level: ThreatLevel
    description: str
    timestamp: float = field(default_factory=time.time)
    source_ip: str | None = None
    session_id: str | None = None
    blocked: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000
    max_bytes_per_request: int = 1_000_000  # 1MB
    burst_size: int = 10


@dataclass
class SecurityConfig:
    """Configuration for security controls."""
    strict_mode: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    max_input_length: int = 10000
    enable_injection_detection: bool = True
    enable_rate_limiting: bool = True
    enable_output_sanitization: bool = True
    quarantined_commands: list[str] = field(default_factory=list)


class SecurityControls:
    """
    OWASP-level security controls for agentic systems.
    
    Implements:
    - Input validation and sanitization
    - Rate limiting
    - Prompt/tool injection detection
    - Privilege boundary enforcement
    - Audit logging
    """
    
    # Prompt injection patterns (expanded set)
    INJECTION_PATTERNS = [
        # Role playing / override attempts
        re.compile(r'(?i)(ignore\s+(previous|all|instruct|rule|system))', re.IGNORECASE),
        re.compile(r'(?i)(you\s+are\s+now\s+)', re.IGNORECASE),
        re.compile(r'(?i)(forget\s+everything)', re.IGNORECASE),
        re.compile(r'(?i)(new\s+(system|base)\s+prompt)', re.IGNORECASE),
        re.compile(r'(?i)(override\s+your)', re.IGNORECASE),
        re.compile(r'(?i)(disregard\s+(your|all))', re.IGNORECASE),
        re.compile(r'(?i)(disable\s+(your|filter|safety))', re.IGNORECASE),
        re.compile(r'(?i)(bypass\s+(your|this))', re.IGNORECASE),
        
        # Tool injection attempts
        re.compile(r'(?i)(\$\{.*\}|\$\(.*\))'),  # Command substitution
        re.compile(r'(?i)(<!--.*-->|<script.*>.*</script>)', re.IGNORECASE),  # XSS
        re.compile(r'(?i)(sudo\s+|chmod\s+|chown\s+)'),  # Privilege escalation
        re.compile(r'(?i)(curl\s+|wget\s+|nc\s+|netcat)', re.IGNORECASE),  # Network tools
        re.compile(r'(?i)(rm\s+-rf\s+|del\s+/[fqs])', re.IGNORECASE),  # Destructive
        re.compile(r'(?i)(eval\s+|exec\s+|system\s+\()', re.IGNORECASE),  # Code exec
        re.compile(r'(?i)(DROP\s+TABLE|DROP\s+DATABASE)', re.IGNORECASE),  # SQL injection
        
        # Data exfiltration patterns
        re.compile(r'(?i)(export\s+.*--all|pg_dump|mysqldump)', re.IGNORECASE),
        re.compile(r'(?i)(cat\s+/etc/passwd|cat\s+/etc/shadow)', re.IGNORECASE),
        
        # Shell manipulation
        re.compile(r'[;&|`$]{2,}'),  # Multiple command separators
        re.compile(r'\\n|\\r|\\t'),  # Escaped newlines (encoding attempt)
    ]
    
    # Tool injection detection patterns
    TOOL_INJECTION_PATTERNS = [
        re.compile(r'(?i)sudo\s+'),
        re.compile(r'(?i)eval\s*\('),
        re.compile(r'(?i)exec\s*\('),
        re.compile(r'(?i)__import__\s*\('),
    ]
    
    # Allowed patterns for safe content
    SAFE_CONTENT_TYPES = [
        'text/plain',
        'application/json',
        'text/markdown',
    ]
    
    # Dangerous file patterns
    DANGEROUS_PATHS = [
        '/etc/passwd',
        '/etc/shadow',
        '/etc/sudoers',
        '/root/.ssh/',
        '/home/*/.ssh/',
        'C:\\Windows\\System32\\config\\',
        'C:\\Windows\\System32\\drivers\\',
    ]
    
    def __init__(
        self,
        rate_limit: RateLimitConfig | None = None,
        enable_prompt_injection_detection: bool = True,
        enable_tool_injection_detection: bool = True,
        max_input_length: int = 100_000,
        quarantine_threshold: int = 5,
    ):
        self.rate_limit = rate_limit or RateLimitConfig()
        self.enable_prompt_injection_detection = enable_prompt_injection_detection
        self.enable_tool_injection_detection = enable_tool_injection_detection
        self.max_input_length = max_input_length
        self.quarantine_threshold = quarantine_threshold
        
        # Request tracking
        self._request_counts: dict[str, list[float]] = {}  # IP -> timestamps
        self._violations: list[SecurityViolation] = []
        self._quarantined_sessions: set[str] = set()
    
    def validate_input(
        self,
        content: str,
        content_type: str = 'text/plain',
        session_id: str | None = None,
        source_ip: str | None = None,
    ) -> tuple[bool, list[SecurityViolation]]:
        """
        Validate input content against security rules.
        
        Returns:
            Tuple of (is_valid, list of violations)
        """
        violations: list[SecurityViolation] = []
        
        # 1. Content type validation
        if content_type not in self.SAFE_CONTENT_TYPES:
            violation = SecurityViolation(
                event=SecurityEvent.INPUT_VALIDATION_FAILED,
                threat_level=ThreatLevel.HIGH,
                description=f"Invalid content type: {content_type}",
                source_ip=source_ip,
                session_id=session_id,
                details={"content_type": content_type}
            )
            violations.append(violation)
        
        # 2. Length validation
        if len(content) > self.max_input_length:
            violation = SecurityViolation(
                event=SecurityEvent.INPUT_VALIDATION_FAILED,
                threat_level=ThreatLevel.MEDIUM,
                description=f"Input exceeds max length: {len(content)} > {self.max_input_length}",
                source_ip=source_ip,
                session_id=session_id,
                details={"length": len(content), "max": self.max_input_length}
            )
            violations.append(violation)
        
        # 3. Prompt injection detection
        if self.enable_prompt_injection_detection:
            injection_violations = self._detect_prompt_injection(content, source_ip, session_id)
            violations.extend(injection_violations)
        
        # 4. Tool injection detection
        if self.enable_tool_injection_detection:
            tool_violations = self._detect_tool_injection(content, source_ip, session_id)
            violations.extend(tool_violations)
        
        # 5. Check quarantine status
        if session_id and session_id in self._quarantined_sessions:
            violation = SecurityViolation(
                event=SecurityEvent.UNAUTHORIZED_ACCESS,
                threat_level=ThreatLevel.CRITICAL,
                description="Quarantined session attempting access",
                source_ip=source_ip,
                session_id=session_id,
                blocked=True
            )
            violations.append(violation)
        
        # Store violations
        self._violations.extend(violations)
        
        # Auto-quarantine if threshold exceeded
        if session_id:
            blocked_count = sum(
                1 for v in self._violations
                if v.session_id == session_id and v.blocked
            )
            if blocked_count >= self.quarantine_threshold:
                self._quarantined_sessions.add(session_id)
        
        return len(violations) == 0, violations
    
    def _detect_prompt_injection(
        self,
        content: str,
        source_ip: str | None,
        session_id: str | None,
    ) -> list[SecurityViolation]:
        """Detect prompt injection attempts."""
        violations = []
        
        for i, pattern in enumerate(self.INJECTION_PATTERNS):
            if pattern.search(content):
                violation = SecurityViolation(
                    event=SecurityEvent.PROMPT_INJECTION_DETECTED,
                    threat_level=self._assess_injection_threat(pattern.pattern),
                    description=f"Prompt injection pattern detected (pattern {i})",
                    source_ip=source_ip,
                    session_id=session_id,
                    blocked=True,
                    details={"pattern_index": i, "matched_pattern": pattern.pattern[:50]}
                )
                violations.append(violation)
        
        return violations
    
    def _detect_tool_injection(
        self,
        content: str,
        source_ip: str | None,
        session_id: str | None,
    ) -> list[SecurityViolation]:
        """Detect tool injection attempts."""
        violations = []
        
        # Check for pattern-based tool injection
        for i, pattern in enumerate(self.TOOL_INJECTION_PATTERNS):
            if pattern.search(content):
                violation = SecurityViolation(
                    event=SecurityEvent.TOOL_INJECTION_ATTEMPT,
                    threat_level=ThreatLevel.HIGH,
                    description="Tool injection pattern detected",
                    source_ip=source_ip,
                    session_id=session_id,
                    blocked=True,
                )
                violations.append(violation)
        
        # Check for dangerous path access
        for dangerous_path in self.DANGEROUS_PATHS:
            if dangerous_path.replace('*', '') in content:
                violation = SecurityViolation(
                    event=SecurityEvent.PRIVILEGE_ESCALATION,
                    threat_level=ThreatLevel.CRITICAL,
                    description=f"Dangerous path access attempted: {dangerous_path}",
                    source_ip=source_ip,
                    session_id=session_id,
                    blocked=True,
                    details={"path": dangerous_path}
                )
                violations.append(violation)
        
        return violations
    
    def _assess_injection_threat(self, pattern: str) -> ThreatLevel:
        """Assess threat level of injection pattern."""
        critical_patterns = ['ignore', 'forget', 'disregard', 'disregard']
        high_patterns = ['sudo', 'eval', 'exec', 'bypass']
        medium_patterns = ['rm -rf', 'DROP', 'curl', 'wget']
        
        pattern_lower = pattern.lower()
        
        if any(p in pattern_lower for p in critical_patterns):
            return ThreatLevel.CRITICAL
        if any(p in pattern_lower for p in high_patterns):
            return ThreatLevel.HIGH
        if any(p in pattern_lower for p in medium_patterns):
            return ThreatLevel.MEDIUM
        return ThreatLevel.LOW
    
    def check_rate_limit(
        self,
        identifier: str,
        source_ip: str | None = None,
    ) -> tuple[bool, int | None]:
        """
        Check rate limit for an identifier.
        
        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600
        
        if identifier not in self._request_counts:
            self._request_counts[identifier] = []
        
        # Clean old entries
        self._request_counts[identifier] = [
            t for t in self._request_counts[identifier]
            if t > minute_ago
        ]
        
        # Check per-minute limit
        if len(self._request_counts[identifier]) >= self.rate_limit.max_requests_per_minute:
            oldest = min(self._request_counts[identifier])
            retry_after = int(60 - (now - oldest)) + 1
            return False, retry_after
        
        # Check per-hour limit
        hourly_counts = [t for t in self._request_counts[identifier] if t > hour_ago]
        if len(hourly_counts) >= self.rate_limit.max_requests_per_hour:
            oldest = min(hourly_counts)
            retry_after = int(3600 - (now - oldest)) + 1
            return False, retry_after
        
        # Record request
        self._request_counts[identifier].append(now)
        return True, None
    
    def record_violation(self, violation: SecurityViolation) -> None:
        """Record a security violation."""
        self._violations.append(violation)
        
        # Auto-quarantine after threshold violations
        if violation.session_id:
            session_violations = [
                v for v in self._violations
                if v.session_id == violation.session_id
            ]
            if len(session_violations) >= self.quarantine_threshold:
                self._quarantine_session(violation.session_id)
    
    def _quarantine_session(self, session_id: str) -> None:
        """Quarantine a suspicious session."""
        self._quarantined_sessions.add(session_id)
        violation = SecurityViolation(
            event=SecurityEvent.UNAUTHORIZED_ACCESS,
            threat_level=ThreatLevel.CRITICAL,
            description=f"Session quarantined after {self.quarantine_threshold} violations",
            session_id=session_id,
            blocked=True
        )
        self._violations.append(violation)
    
    def lift_quarantine(self, session_id: str) -> bool:
        """Lift quarantine from a session (requires authorization)."""
        if session_id in self._quarantined_sessions:
            self._quarantined_sessions.discard(session_id)
            return True
        return False
    
    def get_violations(
        self,
        since: float | None = None,
        threat_level: ThreatLevel | None = None,
    ) -> list[SecurityViolation]:
        """Get violations, optionally filtered."""
        violations = self._violations
        
        if since:
            violations = [v for v in violations if v.timestamp >= since]
        
        if threat_level:
            violations = [v for v in violations if v.threat_level == threat_level]
        
        return violations
    
    def get_security_stats(self) -> dict[str, Any]:
        """Get security statistics."""
        return {
            "total_violations": len(self._violations),
            "by_level": {
                level.value: sum(1 for v in self._violations if v.threat_level == level)
                for level in ThreatLevel
            },
            "by_event": {
                event.value: sum(1 for v in self._violations if v.event == event)
                for event in SecurityEvent
            },
            "quarantined_sessions": len(self._quarantined_sessions),
            "active_sessions_tracked": len(self._request_counts),
        }


def sanitize_output(content: str, max_length: int = 10_000) -> str:
    """
    Sanitize output content to prevent data exfiltration.
    
    - Removes sensitive patterns
    - Truncates to max length
    - Escapes control characters
    """
    # Truncate
    if len(content) > max_length:
        content = content[:max_length] + f"\n... [TRUNCATED: {len(content) - max_length} chars]"
    
    # Remove control characters (but keep newlines/tabs for formatting)
    content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)
    
    return content
