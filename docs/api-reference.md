# API Reference

Complete API reference for the Hermes-Pi Bridge protocol.

## JSON-RPC 2.0

All messages follow [JSON-RPC 2.0](https://www.jsonrpc.org/specification) specification.

### Request

```json
{
  "jsonrpc": "2.0",
  "method": "method.name",
  "params": { ... },
  "id": 1
}
```

### Response (Success)

```json
{
  "jsonrpc": "2.0",
  "result": { ... },
  "id": 1
}
```

### Response (Error)

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32600,
    "message": "Error description",
    "data": { ... }
  },
  "id": 1
}
```

---

## Error Codes

| Code | Constant | Description |
|------|----------|-------------|
| -32700 | `PARSE_ERROR` | Invalid JSON |
| -32600 | `INVALID_REQUEST` | Invalid request format |
| -32601 | `METHOD_NOT_FOUND` | Unknown method |
| -32602 | `INVALID_PARAMS` | Invalid parameters |
| -32603 | `INTERNAL_ERROR` | Internal error |
| 1001 | `TIMEOUT` | Task timed out |
| 1002 | `AUTH_FAILED` | Authentication failed |
| 1003 | `PI_UNAVAILABLE` | pi agent not available |
| 1004 | `INVALID_TASK_STATE` | Invalid task state transition |
| 1005 | `RATE_LIMITED` | Too many requests |

---

## Agent Endpoints

### POST `/api/v1/agent.status`

Check if the remote agent is available and healthy.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "agent.status",
  "params": {
    "agent_id": "hermes-1"
  },
  "id": 1
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "available": true,
    "version": "1.0.0",
    "active_tasks": 2,
    "max_concurrent": 5,
    "timestamp": 1716057600
  },
  "id": 1
}
```

---

## Task Endpoints

### POST `/api/v1/task.delegate`

Delegate a task to the remote agent.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "task.delegate",
  "params": {
    "title": "Analyze code quality",
    "description": "Review this Python codebase for bugs",
    "context": {
      "language": "python",
      "repo_url": "https://github.com/example/repo"
    },
    "timeout_seconds": 300,
    "priority": "normal"
  },
  "id": 2
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "task_id": "task-uuid-here",
    "status": "pending",
    "created_at": 1716057600
  },
  "id": 2
}
```

---

### POST `/api/v1/task.result`

Submit or receive task result.

**Request (submit result):**
```json
{
  "jsonrpc": "2.0",
  "method": "task.result",
  "params": {
    "task_id": "task-uuid-here",
    "status": "success",
    "artifacts": [
      {
        "type": "file",
        "path": "/results/report.md",
        "description": "Analysis report"
      }
    ],
    "summary": "Analysis complete. Found 3 issues."
  },
  "id": 3
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "acknowledged": true,
    "task_id": "task-uuid-here"
  },
  "id": 3
}
```

---

### POST `/api/v1/task.status`

Get the status of a task.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "task.status",
  "params": {
    "task_id": "task-uuid-here"
  },
  "id": 4
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "task_id": "task-uuid-here",
    "status": "running",
    "created_at": 1716057600,
    "started_at": 1716057610,
    "progress": {
      "current": 2,
      "total": 5,
      "message": "Analyzing files..."
    }
  },
  "id": 4
}
```

### Status Values

| Status | Description |
|--------|-------------|
| `pending` | Task received, waiting to start |
| `running` | Task is being executed |
| `success` | Task completed successfully |
| `failure` | Task failed |
| `partial` | Task completed with errors |
| `cancelled` | Task was cancelled |
| `blocked` | Task blocked due to failures |

---

### POST `/api/v1/task.cancel`

Cancel a running or pending task.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "task.cancel",
  "params": {
    "task_id": "task-uuid-here"
  },
  "id": 5
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "task_id": "task-uuid-here",
    "status": "cancelled",
    "cancelled_at": 1716057800
  },
  "id": 5
}
```

---

## Agent-Specific Endpoints

### POST `/api/v1/agent.ready` (Hermes only)

pi notifies Hermes that it's ready to receive tasks.

```json
{
  "jsonrpc": "2.0",
  "method": "agent.ready",
  "params": {
    "agent_id": "pi-1",
    "version": "1.0.0",
    "capabilities": ["task.delegate", "task.result"]
  },
  "id": 6
}
```

---

## Type Definitions

### TaskDelegateRequest

```typescript
interface TaskDelegateRequest {
  title: string;           // Required, 1-500 chars
  description?: string;   // Optional, max 10000 chars
  context?: Record<string, unknown>;
  timeout_seconds?: number; // Default: 300, range: 10-3600
  priority?: "low" | "normal" | "high" | "urgent";
}
```

### TaskResult

```typescript
interface TaskResult {
  task_id: string;
  status: "success" | "failure" | "partial";
  artifacts?: Artifact[];
  summary: string;
  errors?: string[];
  checkpoint_hash?: string;
  duration_seconds?: number;
}

interface Artifact {
  type: "file" | "directory" | "url" | "data";
  path?: string;
  url?: string;
  data?: unknown;
  description?: string;
}
```

### AgentStatus

```typescript
interface AgentStatus {
  available: boolean;
  version: string;
  active_tasks: number;
  max_concurrent: number;
  timestamp: number;
}
```

---

## Authentication

Include Bearer token in `Authorization` header:

```
Authorization: Bearer <your-token>
```

---

## Rate Limits

| Plan | Requests/second | Burst |
|------|-----------------|-------|
| Default | 10 | 20 |

---

## Examples

### cURL

```bash
# Check agent status
curl -X POST http://localhost:2719/api/v1/agent.status \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{"jsonrpc": "2.0", "method": "agent.status", "params": {}, "id": 1}'

# Delegate task
curl -X POST http://localhost:2719/api/v1/task.delegate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "jsonrpc": "2.0",
    "method": "task.delegate",
    "params": {
      "title": "Analyze this code",
      "description": "Find bugs in main.py",
      "timeout_seconds": 300
    },
    "id": 2
  }'
```

### Python

```python
import httpx

client = httpx.Client(
    base_url="http://localhost:2719",
    headers={"Authorization": "Bearer your-token"}
)

# Check status
response = client.post("/api/v1/agent.status", json={
    "jsonrpc": "2.0",
    "method": "agent.status",
    "params": {"agent_id": "hermes-1"},
    "id": 1
})
print(response.json())

# Delegate task
response = client.post("/api/v1/task.delegate", json={
    "jsonrpc": "2.0",
    "method": "task.delegate",
    "params": {
        "title": "Analyze code",
        "timeout_seconds": 300
    },
    "id": 2
})
print(response.json())
```

### TypeScript

```typescript
const response = await fetch('http://localhost:2719/api/v1/task.delegate', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer your-token'
  },
  body: JSON.stringify({
    jsonrpc: '2.0',
    method: 'task.delegate',
    params: {
      title: 'Analyze code',
      timeout_seconds: 300
    },
    id: 1
  })
});

const data = await response.json();
console.log(data);
```