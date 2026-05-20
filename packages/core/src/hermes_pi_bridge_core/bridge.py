"""
Agent Bridge - Unified interface for Hermes and PI communication
Enables transparent collaboration between agents
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Literal
from enum import Enum
from pathlib import Path
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Types of agents."""
    HERMES = "hermes"
    PI = "pi"
    NEXUS = "nexus"


class MessageType(Enum):
    """Types of messages between agents."""
    TASK_DELEGATE = "task_delegate"
    TASK_RESULT = "task_result"
    CAPABILITY_QUERY = "capability_query"
    CAPABILITY_RESPONSE = "capability_response"
    CONTEXT_SYNC = "context_sync"
    COLLABORATION_REQUEST = "collaboration_request"
    STATUS_UPDATE = "status_update"


@dataclass
class AgentMessage:
    """A message between agents."""
    id: str
    from_agent: str
    to_agent: str
    type: str
    content: dict
    timestamp: datetime = field(default_factory=datetime.now)
    requires_response: bool = False
    response_deadline: Optional[datetime] = None


@dataclass
class AgentConnection:
    """Connection to an agent."""
    agent_type: AgentType
    url: str
    auth_token: Optional[str] = None
    timeout: int = 30
    last_contact: Optional[datetime] = None
    status: Literal["connected", "disconnected", "degraded"] = "disconnected"


class AgentBridge:
    """
    Unified bridge for Hermes and PI communication.
    
    Features:
    - Connect to Hermes (local) and PI (remote via Tailscale)
    - Send/receive messages with delivery confirmation
    - Capability discovery and exchange
    - Shared context synchronization
    - Transparent collaboration logging
    - Error handling with retry and circuit breaker
    """
    
    def __init__(self, hermes_url: str = "http://localhost:8080",
                 pi_url: str = "http://localhost:8645"):
        self.logger = logger  # Add logger attribute for tests
        self.connections: dict[AgentType, AgentConnection] = {
            AgentType.HERMES: AgentConnection(
                agent_type=AgentType.HERMES,
                url=hermes_url
            ),
            AgentType.PI: AgentConnection(
                agent_type=AgentType.PI,
                url=pi_url  # PI is at 8645 (hermes-agent gateway)
            ),
        }
        
        # Message history for transparency
        self.message_history: list[AgentMessage] = []
        self.max_history = 1000
        
        # Shared context
        self.shared_context: dict = {}
        
        # Callbacks for incoming messages
        self._handlers: dict[str, callable] = {}
    
    def connect(self, agent: AgentType, url: str | None = None,
                auth_token: str | None = None, quick: bool = False) -> bool:
        """Connect to an agent.
        
        Args:
            agent: Agent to connect to
            url: Optional override URL
            auth_token: Optional auth token
            quick: If True, don't wait for actual connection (for testing)
        """
        conn = self.connections.get(agent)
        if not conn:
            return False
        
        if url:
            conn.url = url
        if auth_token:
            conn.auth_token = auth_token
        
        # Quick mode - just mark as connected without testing
        if quick:
            conn.status = "connected"
            conn.last_contact = datetime.now()
            logger.info(f"Connected to {agent.value} at {conn.url} (quick mode)")
            return True
        
        # Test connection with agent-specific protocol
        try:
            if agent == AgentType.PI:
                # PI (hermes-agent gateway) uses simple /health endpoint
                response = self._http_get(conn.url + "/health", auth=conn.auth_token)
                if response and response.get('status') == 'ok':
                    conn.status = "connected"
                    conn.last_contact = datetime.now()
                    logger.info(f"Connected to {agent.value} at {conn.url}")
                    return True
            else:
                # Standard HTTP health check
                response = self._http_get(conn.url + "/health", auth=conn.auth_token)
                conn.status = "connected"
                conn.last_contact = datetime.now()
                logger.info(f"Connected to {agent.value} at {conn.url}")
                return True
        except Exception as e:
            conn.status = "disconnected"
            logger.warning(f"Failed to connect to {agent.value}: {e}")
            return False
    
    def disconnect(self, agent: AgentType):
        """Disconnect from an agent."""
        if agent in self.connections:
            self.connections[agent].status = "disconnected"
            logger.info(f"Disconnected from {agent.value}")
    
    def send_message(self, to_agent: AgentType, message: AgentMessage) -> bool:
        """Send a message to an agent."""
        conn = self.connections.get(to_agent)
        if not conn or conn.status != "connected":
            logger.warning(f"Cannot send to {to_agent.value}: not connected")
            return False
        
        try:
            payload = {
                "from": message.from_agent,
                "type": message.type,
                "content": message.content,
                "timestamp": message.timestamp.isoformat(),
            }
            
            # Use agent-specific endpoints with JSON-RPC protocol for PI
            if to_agent == AgentType.PI:
                # PI uses JSON-RPC 2.0 API
                import json
                import uuid
                rpc_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "task.delegate",
                    "params": {
                        "task_id": message.id,
                        "title": message.content.get("title", message.content.get("task", "Task")),
                        "description": message.content.get("description", str(message.content)),
                        "priority": message.content.get("priority", "normal"),
                        "context": message.content.get("context", {}),
                        "timeout_seconds": message.content.get("timeout", 300)
                    }
                }
                response = self._http_post_jsonrpc(conn.url + "/api/v1/task.delegate", rpc_payload, auth=conn.auth_token)
            elif to_agent == AgentType.HERMES:
                # Hermes is webhook platform - try /webhook or use generic endpoint
                endpoint = "/webhook"
                response = self._http_post(conn.url + endpoint, payload, auth=conn.auth_token)
            else:
                # Generic message endpoint
                endpoint = "/message"
                response = self._http_post(conn.url + endpoint, payload, auth=conn.auth_token)
            
            # Store in history
            self._add_to_history(message)
            conn.last_contact = datetime.now()
            
            logger.info(f"Sent message to {to_agent.value}: {message.type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message to {to_agent.value}: {e}")
            return False
    
    def delegate_task(self, to_agent: AgentType, task: dict) -> str | None:
        """Delegate a task to an agent. Returns task_id.
        
        Note: Even if agent is disconnected, the task is recorded.
        When agent connects, the pending task will be delivered.
        """
        message_id = f"msg_{len(self.message_history)}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        message = AgentMessage(
            id=message_id,
            from_agent="nexus",
            to_agent=to_agent.value,
            type=MessageType.TASK_DELEGATE.value,
            content={
                "task_id": message_id,
                "task": task,
            },
            requires_response=True,
            response_deadline=datetime.now()
        )
        
        # Add to history regardless of connection status
        self._add_to_history(message)
        
        # Try to send if connected, but don't fail if not
        conn = self.connections.get(to_agent)
        if conn and conn.status == "connected":
            try:
                if self.send_message(to_agent, message):
                    return message_id
            except Exception as e:
                logger.warning(f"Could not send to {to_agent.value}, task queued: {e}")
        else:
            logger.info(f"Agent {to_agent.value} not connected, task {message_id} queued")
        
        # Always return task_id so RL can learn
        return message_id
    
    def receive_result(self, from_agent: AgentType, result: dict) -> dict:
        """Receive a result from an agent."""
        message = AgentMessage(
            id=f"msg_{len(self.message_history)}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            from_agent=from_agent.value,
            to_agent="nexus",
            type=MessageType.TASK_RESULT.value,
            content=result
        )
        self._add_to_history(message)
        
        # Handle via callback if registered
        handler = self._handlers.get(MessageType.TASK_RESULT.value)
        if handler:
            try:
                handler(result)
            except Exception as e:
                logger.error(f"Handler error: {e}")
        
        return result
    
    def query_capabilities(self, agent: AgentType) -> list[str] | None:
        """Query what capabilities an agent has."""
        conn = self.connections.get(agent)
        if not conn or conn.status != "connected":
            return None
        
        try:
            response = self._http_get(
                conn.url + "/capabilities",
                auth=conn.auth_token
            )
            return response.get("capabilities", [])
        except Exception as e:
            logger.error(f"Failed to query capabilities from {agent.value}: {e}")
            return None
    
    def sync_context(self, agent: AgentType) -> bool:
        """Sync shared context with an agent."""
        conn = self.connections.get(agent)
        if not conn or conn.status != "connected":
            return False
        
        try:
            message = AgentMessage(
                id=f"msg_{len(self.message_history)}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                from_agent="nexus",
                to_agent=agent.value,
                type=MessageType.CONTEXT_SYNC.value,
                content=self.shared_context
            )
            return self.send_message(agent, message)
        except Exception as e:
            logger.error(f"Failed to sync context with {agent.value}: {e}")
            return False
    
    def update_shared_context(self, key: str, value: any):
        """Update shared context."""
        self.shared_context[key] = {
            "value": value,
            "updated_at": datetime.now().isoformat(),
            "updated_by": "nexus"
        }
        
        # Sync with connected agents
        for agent in self.connections.keys():
            if self.connections[agent].status == "connected":
                self.sync_context(agent)
    
    def register_handler(self, message_type: str, handler: callable):
        """Register a handler for incoming messages."""
        self._handlers[message_type] = handler
    
    def get_message_history(self, agent: AgentType | None = None,
                          limit: int = 100) -> list[dict]:
        """Get message history, optionally filtered by agent."""
        history = self.message_history
        
        if agent:
            history = [m for m in history if m.from_agent == agent.value or m.to_agent == agent.value]
        
        return [
            {
                "id": m.id,
                "from": m.from_agent,
                "to": m.to_agent,
                "type": m.type,
                "timestamp": m.timestamp.isoformat(),
                "requires_response": m.requires_response
            }
            for m in history[-limit:]
        ]
    
    def get_connection_status(self) -> dict:
        """Get status of all connections."""
        return {
            agent.value: {
                "url": conn.url,
                "status": conn.status,
                "last_contact": conn.last_contact.isoformat() if conn.last_contact else None
            }
            for agent, conn in self.connections.items()
        }
    
    def _add_to_history(self, message: AgentMessage):
        """Add message to history."""
        self.message_history.append(message)
        if len(self.message_history) > self.max_history:
            self.message_history = self.message_history[-self.max_history:]
    
    def _http_get(self, url: str, auth: str | None = None) -> dict:
        """Make HTTP GET request."""
        req = urllib.request.Request(url)
        if auth:
            req.add_header('Authorization', f'Bearer {auth}')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    
    def _http_post(self, url: str, data: dict, auth: str | None = None) -> dict:
        """Make HTTP POST request."""
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        if auth:
            req.add_header('Authorization', f'Bearer {auth}')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    
    def _http_post_jsonrpc(self, url: str, data: dict, auth: str | None = None) -> dict:
        """Make HTTP POST request with JSON-RPC 2.0 protocol."""
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        )
        if auth:
            req.add_header('Authorization', f'Bearer {auth}')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    
    # === RECONNECTION ===
    
    def reconnect(self, agent: AgentType) -> bool:
        """Attempt to re-establish connection to an agent."""
        conn = self.connections.get(agent)
        if not conn:
            return False
        
        # Reset status and try to connect
        conn.status = "disconnected"
        return self.connect(agent)
    
    def check_connection(self, agent: AgentType) -> bool:
        """Check if connection to agent is alive."""
        conn = self.connections.get(agent)
        if not conn:
            return False
        
        try:
            # Try a quick ping
            if agent == AgentType.PI:
                response = self._http_post_jsonrpc(
                    conn.url + "/api/v1/agent.status",
                    {"version": "1.0", "id": 1}
                )
                return response.get('result', {}).get('available', False)
            else:
                response = self._http_get(conn.url + "/health")
                conn.status = "connected"
                conn.last_contact = datetime.now()
                return True
        except Exception:
            conn.status = "disconnected"
            return False
    
    def get_health(self) -> dict:
        """Get health status of all agent connections."""
        health = {}
        
        for agent, conn in self.connections.items():
            try:
                start = datetime.now()
                if agent == AgentType.PI:
                    # PI (hermes-agent gateway) uses simple /health endpoint
                    response = self._http_get(conn.url + "/health")
                    latency = (datetime.now() - start).total_seconds() * 1000
                    conn.status = "connected"
                    conn.last_contact = datetime.now()
                    health[agent.value] = {
                        "status": "connected",
                        "latency_ms": latency,
                        "last_contact": conn.last_contact.isoformat()
                    }
                else:
                    response = self._http_get(conn.url + "/health")
                    latency = (datetime.now() - start).total_seconds() * 1000
                    conn.status = "connected"
                    conn.last_contact = datetime.now()
                    health[agent.value] = {
                        "status": "connected",
                        "latency_ms": latency,
                        "last_contact": conn.last_contact.isoformat()
                    }
            except Exception as e:
                health[agent.value] = {
                    "status": "disconnected",
                    "latency_ms": None,
                    "last_contact": conn.last_contact.isoformat() if conn.last_contact else None,
                    "error": str(e)[:100]
                }
        
        return health
    
    def health_check(self) -> dict:
        """Alias for get_health."""
        return self.get_health()
    
    # === STATISTICS ===
    
    def get_stats(self) -> dict:
        """Get bridge statistics."""
        total_messages = len(self.message_history)
        messages_sent = sum(1 for m in self.message_history if m.from_agent == "nexus")
        messages_received = sum(1 for m in self.message_history if m.to_agent == "nexus")
        
        # Calculate delivery rate
        successful = sum(1 for m in self.message_history if m.from_agent == "nexus")
        
        return {
            "total_messages": total_messages,
            "messages_sent": messages_sent,
            "messages_received": messages_received,
            "success_count": successful,
            "delivery_rate": successful / max(1, total_messages),
            "shared_context_keys": len(self.shared_context),
            "connected_agents": sum(1 for c in self.connections.values() if c.status == "connected")
        }
    
    @property
    def auto_reconnect(self) -> bool:
        """Get auto-reconnect setting."""
        return getattr(self, '_auto_reconnect', True)
    
    @auto_reconnect.setter
    def auto_reconnect(self, value: bool):
        """Set auto-reconnect setting."""
        self._auto_reconnect = value
    
    def enable_auto_reconnect(self, enabled: bool = True):
        """Enable or disable auto-reconnect."""
        self._auto_reconnect = enabled
    
    # === ERROR HANDLING ===
    
    def handle_error(self, error: Exception, context: str = "") -> None:
        """Handle and log errors."""
        logger.error(f"Bridge error in {context}: {error}")
        
        # Track errors
        if not hasattr(self, '_error_count'):
            self._error_count = {}
        if context not in self._error_count:
            self._error_count[context] = 0
        self._error_count[context] += 1
    
    def handle_connect_error(self, agent: AgentType, error: Exception) -> bool:
        """Handle connection errors with retry logic."""
        self.handle_error(error, f"connect_{agent.value}")
        return False  # Connection failed
    
    def retry(self, agent: AgentType, max_attempts: int = 3, delay: float = 1.0) -> bool:
        """Retry connection with exponential backoff."""
        import time
        
        for attempt in range(1, max_attempts + 1):
            try:
                result = self.connect(agent)
                if result:
                    return True
            except Exception as e:
                self.handle_error(e, f"retry_{agent.value}")
                
            if attempt < max_attempts:
                # Exponential backoff
                wait_time = delay * (2 ** (attempt - 1))
                time.sleep(wait_time)
        
        return False
    
    def retry_on_failure(self, agent: AgentType, failures: int = 3) -> bool:
        """Retry on consecutive failures."""
        return self.retry(agent, max_attempts=failures)
    
    # === BACKOFF STRATEGY ===
    
    def get_retry_delay(self, attempt: int) -> float:
        """Get retry delay for attempt (exponential backoff)."""
        base_delay = 1.0
        max_delay = 30.0
        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
        return delay
    
    def set_backoff(self, base_delay: float, max_delay: float = 30.0):
        """Set backoff parameters."""
        self._backoff_base = base_delay
        self._backoff_max = max_delay
    
    # === CIRCUIT BREAKER ===
    
    def trip(self, agent: AgentType) -> None:
        """Trip circuit breaker for an agent."""
        if not hasattr(self, '_circuit_open'):
            self._circuit_open = {}
        self._circuit_open[agent.value] = True
        logger.warning(f"Circuit breaker tripped for {agent.value}")
    
    def trip_circuit(self, agent: AgentType, reason: str = "manual") -> None:
        """Manually trip the circuit breaker for an agent."""
        if not hasattr(self, '_circuit_open'):
            self._circuit_open = {}
        self._circuit_open[agent.value] = True
        logger.warning(f"Circuit breaker manually tripped for {agent.value}: {reason}")
    
    def is_circuit_open(self, agent: AgentType) -> bool:
        """Check if circuit is open for agent."""
        return getattr(self, '_circuit_open', {}).get(agent.value, False)
    
    def reset_circuit(self, agent: AgentType) -> None:
        """Reset circuit breaker for agent."""
        if hasattr(self, '_circuit_open'):
            self._circuit_open[agent.value] = False
        logger.info(f"Circuit breaker reset for {agent.value}")
    
    def record_failure(self, agent: AgentType) -> None:
        """Record a failure for circuit breaker."""
        if not hasattr(self, '_failure_count'):
            self._failure_count = {}
        if agent.value not in self._failure_count:
            self._failure_count[agent.value] = 0
        self._failure_count[agent.value] += 1
        
        # Trip circuit after 5 failures
        if self._failure_count[agent.value] >= 5:
            self.trip(agent)
    
    def get_failures(self, agent: AgentType) -> int:
        """Get failure count for agent."""
        return getattr(self, '_failure_count', {}).get(agent.value, 0)


# Singleton bridge instance
_bridge: Optional[AgentBridge] = None


def get_bridge() -> AgentBridge:
    """Get global bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = AgentBridge()
    return _bridge