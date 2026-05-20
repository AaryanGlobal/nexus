# Quick Start Guide

Get Hermes and pi talking to each other in under 5 minutes.

## What We're Building

By the end of this guide:
- Hermes can delegate tasks to pi
- pi can report results back to Hermes
- Both agents stay in sync automatically

## Step 1: Install

```bash
git clone https://github.com/your-org/hermes-pi-bridge.git
cd hermes-pi-bridge
./scripts/seed.sh
```

The script detects both agents and installs the right parts.

## Step 2: Restart Your Agents

Both agents need to reload their plugins/extensions.

**Hermes:**
```bash
# Restart Hermes agent
# The plugin loads automatically on startup
```

**pi:**
```bash
# Restart pi
# It picks up the new package from settings.json
```

## Step 3: Verify It's Working

In Hermes:
```bash
/pi_status
```

You should see `available: true`. If not, check that both bridge servers are running (they start automatically when agents load).

## Step 4: Try Delegation

### From Hermes to pi

Say you're working in Hermes and want to offload something to pi:

```bash
/pi_delegate task="Run a security scan on this repository" timeout=300
```

What happens:
1. Task appears in Hermes Kanban as "pending"
2. Request goes to pi's bridge server
3. pi picks it up and starts working
4. When done, results flow back
5. Kanban updates to "done"

### From pi to Hermes

Working in pi and need Hermes to do something?

```typescript
// In pi, after installing the extension
const result = await hermes_delegate({
  task: "Refactor this function for better performance",
  context: {
    file: "src/processing.py",
    function: "handle_request"
  }
});

console.log(result);
// { task_id: "abc-123", status: "delegated" }
```

## Real-World Examples

### Example 1: Code Review

**Scenario:** You're in Hermes reviewing a PR and need pi to run tests.

```bash
/pi_delegate task="Run test suite on this branch" context="git checkout feature-xyz && npm test" timeout=600
```

pi runs the tests, results come back. You continue reviewing with test results in hand.

### Example 2: Research Handoff

**Scenario:** pi is working on documentation and needs Hermes' code analysis.

```typescript
// In pi
const analysis = await hermes_delegate({
  task: "Analyze this code for documentation gaps",
  context: {
    files: ["src/**/*.py"],
    focus: "public_api"
  }
});

// Use the analysis to write docs
```

### Example 3: Parallel Work

**Scenario:** You want Hermes to refactor one part while pi handles tests.

```bash
# In Hermes
/pi_delegate task="Write integration tests for auth module" priority=high

# Then do other work in Hermes while pi works
```

## Monitoring Tasks

### Check Status in Hermes

```bash
/pi_status
# Shows: available, active_tasks, max_concurrent
```

### View Kanban

Hermes' Kanban board shows all delegated tasks automatically:
- Pending → Running → Done/Failed/Blocked

### Cancel a Task

```bash
# From Hermes
/pi_cancel task_id="abc-123"

# Or from pi
const cancelled = await fetch('http://localhost:8080/api/v1/task.cancel', {
  method: 'POST',
  body: JSON.stringify({
    jsonrpc: '2.0',
    method: 'task.cancel',
    params: { task_id: 'abc-123' },
    id: 1
  })
});
```

## Common Issues

### pi Shows Unavailable

1. Check pi bridge server is running:
   ```bash
   curl http://localhost:2719/api/v1/health
   ```

2. Check Hermes can reach it:
   ```bash
   curl http://localhost:8080/api/v1/health
   ```

3. Restart the agents.

### Task Never Completes

- Timeout might be too short. Try increasing `timeout_seconds`.
- Check pi's workload with `/pi_status`.
- Look at pi's logs for errors.

### Results Not Returning

- Both agents need network access to each other's ports (8080 and 2719).
- Check firewall rules.
- Verify auth tokens match if configured.

## Next Steps

- Read the [Architecture docs](./architecture.md) to understand how it works
- Check [API Reference](./api-reference.md) for programmatic access
- Customize the bridge in your config files

## Need Help?

- Open an issue on GitHub
- Check existing issues first
- Include your agent versions and what you were trying to do
