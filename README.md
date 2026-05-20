# Nexus - PI-Hermes Bridge

> A bidirectional bridge for intelligent collaboration between PI and Hermes agents.

---

## What It Does

Nexus connects PI and Hermes agents, enabling them to:

- Delegate tasks to the optimal agent
- Share context across agent boundaries
- Track goals and learn from outcomes
- Self-evolve through capability proposals

## Quick Start

```bash
# Install
pip install -e packages/core

# Check status
nexus status

# Start API server
python nexus_server.py
```

## For Developers

```bash
# CLI commands
nexus status         # System status
nexus capabilities   # Agent capabilities
nexus pillars       # Life pillars
nexus goals         # Track objectives

# API endpoints
GET  /health        # Health check
GET  /status        # Full status
POST /delegate      # Route task
POST /result        # Report outcome
```

## For AI Agents

I'm your collaboration layer. Here's how to use me:

### Task Delegation

```python
from hermes_pi_bridge_core.bridge import get_bridge, AgentType

bridge = get_bridge()

# Send to PI (execution, coding)
bridge.delegate_task(AgentType.PI, {
    "type": "implement",
    "content": your_code,
    "constraints": constraints
})

# Send to Hermes (planning, reasoning)
bridge.delegate_task(AgentType.HERMES, {
    "type": "design",
    "content": your_requirements
})

# Receive results
result = bridge.receive_result(AgentType.PI, {"success": True, "output": "..."})
```

### Context Sharing

```python
# Share context with both agents
bridge.update_shared_context("task", "building auth")
bridge.update_shared_context("mode", "TDD")

# Sync when needed
bridge.sync_context(AgentType.HERMES)
```

### Smart Routing

```python
from hermes_pi_bridge_core.life_context import LifeContextEngine

engine = LifeContextEngine()

# I'll route to the best agent
best = engine.route_task(["security", "review"])  # Returns "pi" or "hermes"

# Check capabilities first
caps = engine.get_capabilities("pi")  # What can PI do?
```

### Goal Tracking

```python
# Create a goal
goal = engine.add_goal(
    title="Implement OAuth",
    description="Add OAuth to API",
    pillar="Engineering"
)

# Update as you progress
engine.update_goal_progress(goal.id, 50)

# See where you stand
pillars = engine.get_pillars()
goals = engine.get_goals_by_pillar("Engineering")
```

### Self-Evolution

```python
# Propose a new capability
prop_id = engine.propose_capability("new_skill", "hermes")

# Others vote
engine.vote_capability(prop_id, "pi", True)  # Approved

# If enough votes, it's added
engine.add_capability("hermes", "new_skill")
```

## How It Works

```
Task arrives
     |
     v
+-------------+
| route_task()|  <- Match to agent capability
+-------------+
     |
     v
+-------------+
|delegate_task|  <- Send to PI or Hermes
+-------------+
     |
     v
+-------------+
|receive_result|  <- Get outcome
+-------------+
     |
     v
+-------------+
| RL learns   |  <- Improve next routing
+-------------+
```

## Configuration

| Agent | URL | Strengths |
|-------|-----|-----------|
| Hermes | `http://localhost:8080` | Planning, reasoning, architecture |
| PI | `http://localhost:8645` | Coding, execution, testing |

## Reinforcement Learning

I learn from our work together:

```python
from hermes_pi_bridge_core.rl import ReinforcementLearning, ActionType

rl = ReinforcementLearning()

# After successful collaboration
rl.reward(ActionType.DELEGATE, success=True)

# Check learning
stats = rl.get_stats()
# {"total_rewards": 42, "success_rate": 0.87, "q_values": {...}}
```

## Error Resilience

I don't crash. I handle failures gracefully:

- Connection loss -> Circuit breaker, queue tasks
- Timeouts -> Retry with backoff
- Invalid input -> Clear validation errors

```python
# Check agent health
health = bridge.get_health()
# {"hermes": {"status": "connected", "latency_ms": 5}, "pi": {...}}

# If disconnected, tasks queue until reconnect
```

## Testing

```bash
# All tests
pytest integration/ -v

# 496 tests passing
```

## Project Structure

```
nexus/
├── packages/
│   ├── core/           # hermes-pi-bridge-core
│   │   └── src/hermes_pi_bridge_core/
│   │       ├── bridge.py         # Task delegation
│   │       ├── life_context.py   # Goals, pillars
│   │       └── rl.py            # Learning
│   ├── pi-extension/   # Node.js PI integration
│   └── hermes-plugin/ # Hermes plugin
├── integration/        # Tests
├── nexus_cli.py        # CLI tool
└── nexus_server.py     # HTTP API
```

## Documentation

- [SPEC.md](./SPEC.md) - Technical specification
- [CHANGELOG.md](./CHANGELOG.md) - Version history
- [CONTRIBUTING.md](./CONTRIBUTING.md) - How to contribute

## Security

Security-conscious design inspired by OWASP standards:

- Input validation and sanitization
- Rate limiting (30/min)
- Circuit breaker pattern
- No hardcoded credentials
- No eval/exec code execution
- Tested against OWASP LLM Top 10 categories

---

## License

**MIT License** - Free and open source, like open hearts and sunny afternoons.

Built by [**Aaryan Salman**](https://github.com/AaryanGlobal/) for intelligent collaboration between humans and AI agents.
