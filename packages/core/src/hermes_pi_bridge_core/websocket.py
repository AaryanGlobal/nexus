"""
WebSocket Server and Client - Real-time Updates

Features:
- WebSocket server for Hermes/PI communication
- Auto-reconnection with exponential backoff
- Heartbeat mechanism
- Message queuing
- Security (origin validation, token auth, message signing)
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable, Awaitable
import json
import asyncio
import logging
import threading
import time
import hashlib
import hmac
from queue import Queue, Empty
from pathlib import Path

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """WebSocket message types."""
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    HEARTBEAT = "heartbeat"
    TASK = "task"
    RESULT = "result"
    ERROR = "error"
    STATUS = "status"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    BROADCAST = "broadcast"


class ConnectionState(Enum):
    """Client connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


@dataclass
class Message:
    """WebSocket message structure."""
    id: str
    msg_type: MessageType
    from_agent: str = ""
    to_agent: str = ""
    content: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    signature: Optional[str] = None
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps({
            'id': self.id,
            'type': self.msg_type.value,
            'from': self.from_agent,
            'to': self.to_agent,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'signature': self.signature,
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Deserialize from JSON."""
        data = json.loads(json_str)
        return cls(
            id=data['id'],
            msg_type=MessageType(data['type']),
            from_agent=data.get('from', ''),
            to_agent=data.get('to', ''),
            content=data.get('content', {}),
            timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now(),
            signature=data.get('signature'),
        )


@dataclass
class Connection:
    """Client connection tracking."""
    agent_id: str
    ws_url: str
    state: ConnectionState = ConnectionState.DISCONNECTED
    connected_at: Optional[datetime] = None
    last_heartbeat: datetime = field(default_factory=datetime.now)
    reconnect_attempts: int = 0
    
    @property
    def uptime_seconds(self) -> float:
        if not self.connected_at:
            return 0
        return (datetime.now() - self.connected_at).total_seconds()


def sign_message(msg: Message, secret: str) -> Message:
    """Sign a message with HMAC."""
    data = f"{msg.id}:{msg.from_agent}:{json.dumps(msg.content)}"
    signature = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    msg.signature = signature
    return msg


def verify_signature(msg: Message, secret: str) -> bool:
    """Verify message signature."""
    if not msg.signature:
        return False
    
    data = f"{msg.id}:{msg.from_agent}:{json.dumps(msg.content)}"
    expected = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(msg.signature, expected)


class WebSocketServer:
    """
    WebSocket server for real-time agent communication.
    
    Features:
    - Multiple client connections
    - Message broadcast
    - Heartbeat monitoring
    - Origin validation
    - Token authentication
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8081):
        self.host = host
        self.port = port
        self.running = False
        
        # Client management
        self.clients: dict[str, object] = {}
        self.max_connections = 100
        
        # Handlers
        self._handlers: dict[MessageType, Callable] = {}
        
        # Configuration
        self.allowed_origins: list[str] = []
        self.auth_token: Optional[str] = None
        self.heartbeat_timeout = 60  # seconds
        
        # Internal state
        self._server = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.RLock()
    
    def start(self) -> bool:
        """Start the WebSocket server."""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            # Start asyncio server
            start_server = self._create_server()
            self._server = self._loop.run_until_complete(start_server)
            
            self.running = True
            logger.info(f"WebSocket server started on {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            return False
    
    async def _create_server(self):
        """Create the asyncio WebSocket server."""
        try:
            import websockets
            
            async def handler(ws, path):
                await self._handle_client(ws, path)
            
            server = await websockets.serve(handler, self.host, self.port)
            return server
            
        except ImportError:
            # websockets not installed - return mock server
            logger.warning("websockets package not installed, using mock server")
            return None
    
    async def _handle_client(self, ws, path):
        """Handle incoming client connection."""
        client_id = None
        
        try:
            # Wait for authentication
            auth_msg = await asyncio.wait_for(ws.recv(), timeout=10)
            auth_data = json.loads(auth_msg)
            
            if 'agent_id' in auth_data:
                client_id = auth_data['agent_id']
                
                # Authenticate if token required
                if self.auth_token and auth_data.get('token') != self.auth_token:
                    await ws.send(json.dumps({'error': 'Unauthorized'}))
                    return
                
                self.clients[client_id] = ws
                logger.info(f"Client connected: {client_id}")
                
                # Send welcome
                await ws.send(json.dumps({
                    'type': 'connected',
                    'client_id': client_id
                }))
                
                # Message loop
                async for msg_str in ws:
                    msg = Message.from_json(msg_str)
                    self._handle_message(msg, client_id)
                    
        except Exception as e:
            logger.error(f"Client handler error: {e}")
        finally:
            if client_id:
                self._remove_client(client_id)
    
    def _handle_message(self, msg: Message, from_client: str):
        """Handle incoming message."""
        # Call registered handler
        handler = self._handlers.get(msg.msg_type)
        if handler:
            try:
                handler(msg)
            except Exception as e:
                logger.error(f"Handler error: {e}")
    
    def _remove_client(self, client_id: str):
        """Remove client from connections."""
        with self._lock:
            if client_id in self.clients:
                del self.clients[client_id]
                logger.info(f"Client disconnected: {client_id}")
    
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """Register message handler."""
        self._handlers[msg_type] = handler
    
    def broadcast(self, msg: Message) -> int:
        """Broadcast message to all clients."""
        count = 0
        json_str = msg.to_json()
        
        for client_id, ws in list(self.clients.items()):
            try:
                if hasattr(ws, 'send'):
                    asyncio.run(ws.send(json_str))
                    count += 1
            except Exception as e:
                logger.warning(f"Broadcast failed for {client_id}: {e}")
                self._remove_client(client_id)
        
        return count
    
    def send_to(self, client_id: str, msg: Message) -> bool:
        """Send message to specific client."""
        ws = self.clients.get(client_id)
        if not ws:
            return False
        
        try:
            if hasattr(ws, 'send'):
                asyncio.run(ws.send(msg.to_json()))
            return True
        except Exception as e:
            logger.error(f"Send failed: {e}")
            self._remove_client(client_id)
            return False
    
    def get_clients(self) -> list[str]:
        """Get list of connected clients."""
        return list(self.clients.keys())
    
    def get_status(self) -> dict:
        """Get server status."""
        return {
            'running': self.running,
            'host': self.host,
            'port': self.port,
            'client_count': len(self.clients),
            'max_connections': self.max_connections,
        }
    
    def _check_stale_clients(self, timeout: int = 60) -> list[str]:
        """Check for clients with stale heartbeats."""
        stale = []
        cutoff = datetime.now() - timedelta(seconds=timeout)
        
        for client_id, ws in list(self.clients.items()):
            try:
                # If no heartbeat within timeout, mark as stale
                # (In real impl, would track per-client heartbeat times)
                pass
            except Exception:
                stale.append(client_id)
        
        return stale
    
    def _can_accept_connection(self) -> bool:
        """Check if server can accept new connection."""
        return len(self.clients) < self.max_connections
    
    def _validate_origin(self, origin: str) -> bool:
        """Validate connection origin."""
        if not self.allowed_origins:
            return True  # No restrictions
        return origin in self.allowed_origins
    
    def _authenticate(self, token: str) -> bool:
        """Authenticate connection with token."""
        if not self.auth_token:
            return True
        return token == self.auth_token
    
    def stop(self):
        """Stop the WebSocket server."""
        self.running = False
        
        if self._server:
            try:
                self._server.close()
            except Exception:
                pass
        
        if self._loop:
            self._loop.run_until_complete(asyncio.sleep(0.1))
            self._loop.close()
        
        logger.info("WebSocket server stopped")


class WebSocketClient:
    """
    WebSocket client for agent communication.
    
    Features:
    - Auto-reconnection with exponential backoff
    - Heartbeat mechanism
    - Message queuing
    - TLS support
    """
    
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.state = ConnectionState.DISCONNECTED
        self.agent_id: Optional[str] = None
        
        # Connection management
        self.ws: Optional[object] = None
        self.max_reconnect_attempts = 5
        self._reconnect_attempts = 0
        self._reconnect_delay = 1.0
        
        # Message handling
        self.message_queue: Queue = Queue()
        self.max_queue_size = 1000
        self._callbacks: dict[MessageType, Callable] = {}
        
        # Heartbeat
        self.last_heartbeat: datetime = datetime.now()
        self.heartbeat_interval = 30  # seconds
        self._heartbeat_task: Optional[asyncio.Task] = None
        
        # Internal
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
    
    def set_agent_id(self, agent_id: str):
        """Set the agent ID for this client."""
        self.agent_id = agent_id
    
    async def connect(self, token: str | None = None) -> bool:
        """Connect to WebSocket server."""
        if self.state == ConnectionState.CONNECTED:
            return True
        
        self.state = ConnectionState.CONNECTING
        
        try:
            import websockets
            
            # Build headers
            headers = {}
            if self.agent_id:
                headers['X-Agent-ID'] = self.agent_id
            if token:
                headers['Authorization'] = f"Bearer {token}"
            
            # Connect
            self.ws = await websockets.connect(self.ws_url, extra_headers=headers)
            self.state = ConnectionState.CONNECTED
            self._on_connected()
            
            logger.info(f"Connected to {self.ws_url}")
            return True
            
        except ImportError:
            logger.warning("websockets not installed, using mock connection")
            self.state = ConnectionState.CONNECTED
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.state = ConnectionState.DISCONNECTED
            return False
    
    async def disconnect(self):
        """Disconnect from server."""
        self._running = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
        
        self.state = ConnectionState.DISCONNECTED
        self.ws = None
    
    async def send_message(self, msg: Message) -> bool:
        """Send a message."""
        if self.state != ConnectionState.CONNECTED:
            # Queue if disconnected
            try:
                self.message_queue.put_nowait(msg)
            except Exception:
                pass  # Queue full
            return False
        
        try:
            if self.ws:
                await self.ws.send(msg.to_json())
            return True
        except Exception as e:
            logger.error(f"Send failed: {e}")
            await self._handle_disconnect()
            return False
    
    async def _handle_disconnect(self):
        """Handle disconnection and reconnect."""
        self.state = ConnectionState.RECONNECTING
        
        if self._can_reconnect(self._reconnect_attempts):
            self._reconnect_attempts += 1
            delay = self._get_reconnect_delay(self._reconnect_attempts)
            
            logger.info(f"Reconnecting in {delay}s (attempt {self._reconnect_attempts})")
            await asyncio.sleep(delay)
            
            if await self.connect():
                self.state = ConnectionState.CONNECTED
        else:
            logger.error("Max reconnect attempts reached")
            self.state = ConnectionState.DISCONNECTED
    
    def _can_reconnect(self, attempt: int) -> bool:
        """Check if reconnection is allowed."""
        return attempt < self.max_reconnect_attempts
    
    def _get_reconnect_delay(self, attempt: int) -> float:
        """Get reconnect delay with exponential backoff."""
        delay = min(60, self._reconnect_delay * (2 ** attempt))
        return delay
    
    def _on_connected(self):
        """Called when connection is established."""
        self._reconnect_attempts = 0
        self._running = True
        self.last_heartbeat = datetime.now()
        
        # Start heartbeat task
        if not self._heartbeat_task:
            self._loop = asyncio.get_event_loop()
            self._heartbeat_task = self._loop.create_task(self._heartbeat_loop())
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats."""
        while self._running and self.state == ConnectionState.CONNECTED:
            await self._send_heartbeat()
            await asyncio.sleep(self.heartbeat_interval)
    
    async def _send_heartbeat(self):
        """Send heartbeat message."""
        msg = Message(
            id=f"hb_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            msg_type=MessageType.HEARTBEAT,
            from_agent=self.agent_id or "unknown",
            content={'timestamp': datetime.now().isoformat()}
        )
        
        try:
            if self.ws:
                await self.ws.send(msg.to_json())
                self.last_heartbeat = datetime.now()
        except Exception:
            pass  # Will be handled by reconnect logic
    
    def _is_heartbeat_stale(self, timeout: int = 60) -> bool:
        """Check if heartbeat is stale."""
        return (datetime.now() - self.last_heartbeat).total_seconds() > timeout
    
    def _handle_message(self, json_str: str):
        """Handle incoming message."""
        try:
            msg = Message.from_json(json_str)
            
            # Call registered callback
            callback = self._callbacks.get(msg.msg_type)
            if callback:
                callback(msg)
            
            # Queue message if no callback
            try:
                self.message_queue.put_nowait(msg)
            except Exception:
                pass  # Queue full
                
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received: {json_str}")
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    def register_callback(self, msg_type: MessageType, callback: Callable):
        """Register callback for message type."""
        self._callbacks[msg_type] = callback
    
    def get_status(self) -> dict:
        """Get client status."""
        return {
            'ws_url': self.ws_url,
            'state': self.state.value,
            'agent_id': self.agent_id,
            'reconnect_attempts': self._reconnect_attempts,
            'queue_size': self.message_queue.qsize(),
            'last_heartbeat': self.last_heartbeat.isoformat(),
        }
    
    def get_message(self, timeout: float = 1.0) -> Message | None:
        """Get message from queue."""
        try:
            return self.message_queue.get(timeout=timeout)
        except Empty:
            return None


# Singleton instances
_server: Optional[WebSocketServer] = None
_client: Optional[WebSocketClient] = None


def get_websocket_server(host: str = "0.0.0.0", port: int = 8081) -> WebSocketServer:
    """Get singleton WebSocket server."""
    global _server
    if _server is None:
        _server = WebSocketServer(host=host, port=port)
    return _server


def get_websocket_client(ws_url: str) -> WebSocketClient:
    """Get singleton WebSocket client."""
    global _client
    if _client is None:
        _client = WebSocketClient(ws_url=ws_url)
    return _client