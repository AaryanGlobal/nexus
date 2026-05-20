# Nexus Bridge - AI Agent Guide

**For AI agents (Hermes, PI, and future agents) to leverage the Nexus Bridge**

---

## Overview

Nexus is a **real-time communication bridge** connecting:
- **Hermes** (strategic agent) - Port 8645
- **PI** (tactical agent) - Port 2719
- **Nexus Server** (orchestrator) - Port 8080

```
┌─────────────────────────────────────────────────────────────────────┐
│                         NEXUS BRIDGE                                 │
│                                                                      │
│   HERMES ──────────────┬──────────────┬─────────────── PI           │
│   (Strategy)           │              │               (Tactics)      │
│                        │   NEXUS      │                             │
│   Port: 8645           │   Server     │   Port: 2719                │
│   Protocol: Webhook    │   8080       │   Protocol: JSON-RPC 2.0    │
│                        │              │                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start for AI Agents

### Connecting to Nexus

```python
from hermes_pi_bridge_core.bridge import AgentBridge, AgentType

bridge = AgentBridge()

# Connect to Hermes
bridge.connect(AgentType.HERMES, "http://127.0.0.1:8645", "your_token")

# Connect to PI
bridge.connect(AgentType.PI, "http://localhost:2719", "your_token")

# Check status
status = bridge.get_connection_status()
print(f"Hermes: {status['hermes']['status']}")
print(f"PI: {status['pi']['status']}")
```

### Sending Messages

```python
from hermes_pi_bridge_core.bridge import AgentMessage
from datetime import datetime

# Create message
msg = AgentMessage(
    id="task_001",
    from_agent="hermes",
    to_agent="pi",
    type="task_delegate",
    content={
        "title": "Build feature X",
        "description": "Implement feature X using TDD",
        "priority": "high"
    },
    timestamp=datetime.now()
)

# Send to PI
result = bridge.send_message(AgentType.PI, msg)
print(f"Delivered: {result}")
```

---

## Agent Protocols

### Hermes (Port 8645)

**Protocol**: Webhook (GET for health, POST for messages)

**Endpoints**:
- `GET /health` - Returns `{"status": "ok", "platform": "webhook"}`
- `POST /webhook` - Accepts message payloads

**Example**:
```bash
# Health check
curl http://127.0.0.1:8645/health

# Send message (via Nexus)
curl -X POST http://127.0.0.1:8645/webhook \
  -H "Content-Type: application/json" \
  -d '{"from": "nexus", "type": "task", "content": {...}}'
```

### PI (Port 2719)

**Protocol**: JSON-RPC 2.0

**Endpoints**:
- `POST /api/v1/agent.status` - Check PI availability
- `POST /api/v1/task.delegate` - Delegate task to PI
- `POST /api/v1/task.status` - Check task status
- `POST /api/v1/task.result` - Report task result
- `GET /api/v1/health` - Health check

**Example**:
```bash
# Check status
curl -X POST http://localhost:2719/api/v1/agent.status \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "version": "1.0"}'

# Delegate task
curl -X POST http://localhost:2719/api/v1/task.delegate \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "task_id": "task_001",
    "title": "Build feature",
    "description": "Implement feature X",
    "priority": "high"
  }'
```

---

## Life Context Engine

Nexus tracks **life goals and capabilities** to route tasks intelligently.

### Adding Context

```python
from hermes_pi_bridge_core.life_context import LifeContextEngine

life = LifeContextEngine()

# Add life context
ctx = life.add_context(
    content="Build thought leadership in AI",
    pillar="voice",
    category="goal"
)

# Add goal
goal = life.add_goal(
    title="Build AI Agent",
    description="Create autonomous agent",
    pillar="capacity"
)
```

### Capability Discovery

```python
# Auto-discover capabilities
h_caps = life.discover_capabilities("hermes")
p_caps = life.discover_capabilities("pi")

print(f"Hermes: {h_caps}")
# ['planning', 'strategy', 'reasoning', 'analysis', ...]

print(f"PI: {p_caps}")
# ['coding', 'execution', 'implementation', 'tools', ...]
```

### Context Sharing

```python
# Share context with agents
life.share_context("hermes")
life.share_context("pi")

# Get all shared context
shared = life.get_shared_context()
print(f"Shared: {len(shared)} items")
```

---

## Message Queue & Resilience

Nexus uses **ResilientBridge** for guaranteed message delivery.

### Features:
- **Message persistence** - Messages survive restarts
- **Retry with exponential backoff** - Failed messages retried
- **Circuit breakers** - Prevents cascade failures
- **Dead letter queue** - Failed messages tracked
- **Deduplication** - Prevents duplicate delivery

### Usage:

```python
from hermes_pi_bridge_core.resilient_bridge import get_resilient_bridge

rbridge = get_resilient_bridge()

# Send with guaranteed delivery
msg_id = rbridge.send_message(
    to_agent="pi",
    from_agent="hermes",
    msg_type="task_delegate",
    content={"task": "important"},
    idempotency_key="unique_task_id"
)

# Check status
pending = rbridge.get_pending_count("pi")
print(f"Pending to PI: {pending}")

# Check dead letters
dls = rbridge.get_dead_letters()
print(f"Failed messages: {len(dls)}")

# Circuit breaker state
cb = rbridge.get_circuit_state("pi")
print(f"PI circuit: {'OPEN' if cb['is_open'] else 'CLOSED'}")
```

---

## Task Routing

Nexus can route tasks to the right agent based on capabilities.

```python
# Check if agent can handle task
can_do, missing = life.can_handle_task(
    "hermes", 
    ["planning", "strategy"]
)

if can_do:
    print("Hermes can handle this!")
else:
    print(f"Missing: {missing}")
```

---

## Consensus Voting

New capabilities require **consensus** (2 of 3 agents agree).

```python
# Propose capability
vote_id = life.propose_capability("new_capability", "hermes")

# Vote
life.vote_capability(vote_id, "hermes", True, "Needed for project")
life.vote_capability(vote_id, "pi", True, "Agree")

# Result: capability approved
```

---

## Configuration

All config via `NexusConfig`:

```python
from hermes_pi_bridge_core.config import get_config

config = get_config()

print(f"Rate limit: {config.rate_limit.requests_per_minute}/min")
print(f"Storage: {config.storage.base_path}")
print(f"RL learning rate: {config.rl.learning_rate}")
```

**Environment Variables**:
- `NEXUS_PORT` - Server port (default: 8080)
- `HERMES_URL` - Hermes endpoint
- `PI_URL` - PI endpoint
- `NEXUS_STORAGE` - Storage path

---

## CLI Commands

```bash
# Status
nexus status

# Health
nexus health

# Bridge status
nexus bridge

# Life context
nexus life

# Add context
nexus context <pillar> <content>

# Daemon mode
nexus daemon start|stop|status

# WebSocket
nexus ws --start|--stop|--clients
```

---

## Error Handling

```python
# Circuit breaker
cb = rbridge.get_circuit_state("pi")
if cb['is_open']:
    print("PI is overloaded, queueing messages...")

# Retry logic (automatic)
# Messages retry with exponential backoff: 1s, 2s, 4s, 8s, max 5 attempts

# Dead letter handling
for dl in rbridge.get_dead_letters():
    print(f"Failed: {dl['id']} - {dl['error']}")
    
    # Retry dead letter
    rbridge.retry_dead_letter(dl['id'])
```

---

## Health Monitoring

```python
from hermes_pi_bridge_core.degradation import GracefulDegradation

degradation = GracefulDegradation()
health = degradation.get_component_health("bridge")

print(f"Status: {health['status']}")
print(f"Uptime: {health['uptime_seconds']}")
```

---

## WebSocket (Real-time Updates)

```python
from hermes_pi_bridge_core.websocket import WebSocketServer

ws = WebSocketServer(host="0.0.0.0", port=8765)
await ws.start()

# Clients auto-reconnect on failure
# Heartbeat every 30 seconds
# Messages: task updates, status changes, errors
```

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_life_context.py -v

# Run with coverage
python -m pytest tests/ --cov=hermes_pi_bridge_core
```

---

## Troubleshooting

**PI not responding?**
- Check PI is running: `curl http://localhost:2719/api/v1/health`
- Check circuit breaker: `rbridge.get_circuit_state("pi")`
- Check pending messages: `rbridge.get_pending_count("pi")`

**Hermes not responding?**
- Check Hermes health: `curl http://127.0.0.1:8645/health`
- Hermes is webhook-only - cannot initiate messages

**Messages not delivering?**
- Check dead letters: `rbridge.get_dead_letters()`
- Reset circuit: `rbridge.reset_circuit("pi")`
- Clear pending: `rbridge.clear_pending("pi")`

---

## Examples

### Full Task Delegation

```python
from hermes_pi_bridge_core.bridge import AgentBridge, AgentType, AgentMessage
from hermes_pi_bridge_core.resilient_bridge import get_resilient_bridge
from datetime import datetime

bridge = AgentBridge()
rbridge = get_resilient_bridge()

# Connect
bridge.connect(AgentType.HERMES, "http://127.0.0.1:8645", "token")
bridge.connect(AgentType.PI, "http://localhost:2719", "token")

# Create and send task
task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}"
msg = AgentMessage(
    id=task_id,
    from_agent="hermes",
    to_agent="pi",
    type="task_delegate",
    content={
        "title": "Implement Feature",
        "description": "Build feature X with TDD",
        "priority": "high",
        "context": {"pillar": "capacity", "goal": "Build AI Agent"}
    },
    timestamp=datetime.now()
)

# Send with guaranteed delivery
result = bridge.send_message(AgentType.PI, msg)

# Also queue for resilience
rbridge.send_message(
    to_agent="pi",
    from_agent="hermes",
    msg_type="task_delegate",
    content=msg.content,
    idempotency_key=task_id
)

print(f"Task delegated: {task_id}")
```

### Context Sync

```python
from hermes_pi_bridge_core.life_context import LifeContextEngine

life = LifeContextEngine()

# Add goal
goal = life.add_goal(
    title="Learn Rust",
    description="Master Rust for systems programming",
    pillar="capacity"
)

# Share with both agents
life.share_context("hermes")
life.share_context("pi")

# Update progress
life.update_goal_progress(goal.id, 50.0)

# Check status
status = life.get_status()
print(f"Goals: {status['goals_total']}, Completed: {status['goals_completed']}")
```

---

**Last Updated**: 2026-05-19
**Version**: 1.0.0
**Agents**: Hermes (strategy), PI (tactics)