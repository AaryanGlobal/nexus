# Nexus Bridge Documentation for AI Agents

## Overview

Nexus is a production-ready orchestration bridge connecting **Hermes** (strategic) ↔ **Nexus** (orchestration) ↔ **PI** (tactical).

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           AI AGENTS                                        │
│  🎤 HERMES (Strategic)    ⚡ NEXUS (Bridge)    🔧 PI (Tactical)              │
│  • Goal planning          • Orchestration        • Task execution          │
│  • Strategy              • Governance             • Implementation          │
│  • Context management    • Rate limiting          • Skills execution       │
└────────────────────────────────────────────────────────────────────────────┘

                          ┌─────────────────────┐
                          │   RESILIENT BRIDGE  │
                          │  • Message Queue    │
                          │  • Retry + Backoff  │
                          │  • Circuit Breaker  │
                          │  • Dead Letter Q    │
                          └─────────────────────┘
```

---

## Quick Reference

### Available Commands

```bash
nexus status          # Full dashboard
nexus health          # Component health
nexus bridge          # Resilient bridge status
nexus daemon status   # Daemon mode status
nexus ws --clients    # WebSocket clients
nexus life            # Four Pillars goals
nexus config --show   # Show configuration
```

### Four Pillars

| Pillar | Description | Command |
|--------|-------------|---------|
| 🎤 Voice | Thought leadership, communication | `nexus context voice "goal"` |
| 💰 Prosperity | Financial, business goals | `nexus context prosperity "goal"` |
| 🏆 Credibility | Reputation, expertise | `nexus context credibility "goal"` |
| ⚡ Capacity | Skills, capabilities | `nexus context capacity "goal"` |

---

## For HERMES Agent

### What Hermes Can Do

1. **Delegate Tasks to PI**
```python
from hermes_pi_bridge_core.bridge import get_bridge

bridge = get_bridge()
task_id = bridge.send_task(
    to_agent="pi",
    task_type="implement",
    content={"feature": "user auth", "spec": "..."}
)
```

2. **Request Context from PI**
```python
context = bridge.request_context(
    to_agent="pi",
    query="current_progress_on_login"
)
```

3. **Sync Life Goals**
```python
from hermes_pi_bridge_core.life_context import get_life_context

life = get_life_context()
life.add_context(
    pillar="voice",
    content="Build thought leadership",
    category="goal"
)
```

4. **Propose New Capabilities**
```python
bridge.propose_capability(
    name="new_skill",
    description="Ability to...",
    agent="pi"  # or "hermes"
)
```

### Hermes-Specific Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Full system status |
| `/delegate` | POST | Send task to PI |
| `/sync` | POST | Sync context with PI |

### Hermes Best Practices

1. **Use the Four Pillars** - All goals should map to Voice/Prosperity/Credibility/Capacity
2. **Check Bridge Health** - `nexus bridge` before critical operations
3. **Use Circuit Breaker** - If PI is failing, Hermes should slow down
4. **Idempotent Messages** - Always use idempotency keys for important messages

---

## For PI Agent

### What PI Can Do

1. **Report Task Results**
```python
from hermes_pi_bridge_core.bridge import get_bridge

bridge = get_bridge()
bridge.report_result(
    task_id="task_123",
    status="completed",
    result={"output": "..."}
)
```

2. **Request Clarification**
```python
bridge.send_message(
    to_agent="hermes",
    msg_type="clarification_request",
    content={"task_id": "task_123", "question": "..."}
)
```

3. **Update Capabilities**
```python
from hermes_pi_bridge_core.capabilities import get_capabilities

caps = get_capabilities()
caps.add_capability(
    name="web_scraping",
    description="Scrape websites...",
    confidence=0.9
)
```

4. **Track Progress**
```python
from hermes_pi_bridge_core.life_context import get_life_context

life = get_life_context()
life.update_goal_progress(
    goal_id="goal_123",
    progress=0.75,  # 75%
    note="Implementation complete, testing remaining"
)
```

### PI-Specific Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/result` | POST | Report task result |
| `/health` | GET | Check Hermes health |
| `/capabilities` | GET | List Hermes capabilities |

### PI Best Practices

1. **Always Acknowledge** - Acknowledge messages to help circuit breaker
2. **Send Heartbeats** - Via WebSocket to stay connected
3. **Queue Overflow Handling** - If queue is full, wait before requesting more
4. **Graceful Degradation** - If Hermes is down, continue with cached context

---

## Resilient Bridge Features

### Message Queue
- Messages persist to disk
- Survives restarts
- Automatic retry with backoff

### Circuit Breaker
```
HERMES → [CLOSED] → PI (messages flow)
HERMES → [OPEN] → PI (messages queued)
HERMES → [HALF-OPEN] → PI (test connection)
```

### Dead Letter Queue
Failed messages after max retries go to dead letter queue for manual review:
```bash
nexus bridge  # Shows dead letters
nexus reset-circuit hermes  # Reset if needed
```

### Backpressure
If queue depth exceeds limits, new messages are rejected:
- Per-agent limit: 50 messages
- Global limit: 100 messages

---

## Daemon Mode

Run Nexus as a background service:

```bash
# Start daemon
nexus daemon start

# Check status
nexus daemon status

# Restart
nexus daemon restart

# Stop
nexus daemon stop
```

Daemon features:
- Auto-restart on crash
- Health monitoring
- Log rotation
- PID file management

---

## WebSocket Server

Real-time communication:

```bash
# Start WebSocket server
nexus ws --start

# List connected clients
nexus ws --clients

# Stop server
nexus ws --stop
```

WebSocket URL: `ws://localhost:8081`

Message format:
```json
{
  "id": "msg_123",
  "type": "task",
  "from": "hermes",
  "to": "pi",
  "content": {"task": "..."},
  "timestamp": "2024-01-01T00:00:00"
}
```

---

## Configuration

Environment variables:
```bash
NEXUS_PORT=8080
NEXUS_RATE_PER_MIN=100
NEXUS_RATE_PER_HOUR=2000
NEXUS_BASE_PATH=~/.nexus
NEXUS_EXPLORATION=0.3
```

Or via config file:
```json
{
  "server": {"port": 8080, "host": "0.0.0.0"},
  "rate_limiting": {"per_minute": 100, "per_hour": 2000},
  "exploration_rate": 0.3,
  "daemon": {"auto_restart": true, "max_restarts": 3}
}
```

---

## Error Handling

### Circuit Open
```
Error: Circuit breaker OPEN for PI
Action: Wait, messages will be queued
Manual reset: nexus reset-circuit pi
```

### Rate Limited
```
Warning: Rate limit approaching
Action: Slow down requests
Check: nexus status (shows remaining)
```

### Dead Letter
```
Error: Message delivery failed after 3 attempts
Action: nexus bridge (view dead letters)
Retry: Use bridge.retry_dead_letter(msg_id)
```

---

## Testing

```bash
# Run all tests
python -m pytest packages/core/tests -v

# Specific test file
python -m pytest packages/core/tests/test_resilient_bridge.py -v

# With coverage
python -m pytest packages/core/tests --cov=hermes_pi_bridge_core
```

---

## Troubleshooting

### Bridge Not Responding
1. Check `nexus bridge` status
2. Check circuit breakers
3. Restart daemon: `nexus daemon restart`

### Messages Not Delivered
1. Check dead letter queue: `nexus bridge`
2. Check queue depth (backpressure)
3. Reset circuit: `nexus reset-circuit <agent>`

### High Memory Usage
1. Check daemon health: `nexus daemon status`
2. Restart daemon: `nexus daemon restart`
3. Clear old messages in `~/.nexus/`

---

## Support

For issues:
1. Check logs: `~/.nexus/daemon.log`
2. Run tests: `python -m pytest packages/core/tests`
3. Check component health: `nexus health`