# Hermes-Pi Bridge Protocol Specification

**Version:** 1.0.0
**Status:** Stable

## Overview

JSON-RPC 2.0 over HTTP for bidirectional Hermes-pi communication.

## Transport

- **Protocol:** HTTP/1.1
- **Format:** JSON-RPC 2.0
- **Content-Type:** application/json

## Base URL

```
http://{host}:{port}/api/v1
```

## Message Envelope

### Request
```json
{
  "jsonrpc": "2.0",
  "method": "method.name",
  "params": { ... },
  "id": "unique-id"
}
```

### Response (Success)
```json
{
  "jsonrpc": "2.0",
  "result": { ... },
  "id": "unique-id"
}
```

### Response (Error)
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": 1000,
    "message": "Human readable message",
    "data": { ... }
  },
  "id": "unique-id"
}
```

## Error Codes

| Code | Name | Description |
|------|------|-------------|
| -32700 | Parse Error | Invalid JSON |
| -32600 | Invalid Request | Missing required fields |
| -32601 | Method Not Found | Unknown method |
| -32602 | Invalid Params | Invalid parameter values |
| -32603 | Internal Error | Server error |
| 1000 | Auth Error | Invalid token |
| 1001 | Session Not Found | Unknown session |
| 1002 | Task Not Found | Unknown task |
| 1003 | Timeout | Operation timed out |
| 1004 | Capacity Exceeded | Max concurrent reached |
| 1005 | Version Mismatch | Incompatible version |

## Methods

### agent.status
Check agent availability.

**Request:**
```json
{
  "method": "agent.status",
  "params": {
    "agent_type": "pi|hermes",
    "version": "1.0.0"
  }
}
```

**Response:**
```json
{
  "result": {
    "available": true,
    "version": "1.0.0",
    "capabilities": ["delegate", "status", "result"],
    "max_concurrent": 2
  }
}
```

### task.delegate
Delegate a task.

**Request:**
```json
{
  "method": "task.delegate",
  "params": {
    "task_id": "uuid",
    "title": "string",
    "description": "string",
    "context": {
      "workspace": "/path",
      "files": ["file1.py"],
      "checkpoint_hash": "sha256:..."
    },
    "timeout_seconds": 300
  }
}
```

**Response:**
```json
{
  "result": {
    "task_id": "uuid",
    "status": "accepted"
  }
}
```

### task.result
Report task completion.

**Request:**
```json
{
  "method": "task.result",
  "params": {
    "task_id": "uuid",
    "status": "success|partial|failed|blocked",
    "summary": "Brief summary",
    "artifacts": [{"path": "file.py", "type": "file"}],
    "errors": ["Error if failed"]
  }
}
```

### task.status
Get task status.

**Request:**
```json
{
  "method": "task.status",
  "params": {
    "task_id": "uuid"
  }
}
```

**Response:**
```json
{
  "result": {
    "task_id": "uuid",
    "status": "running|completed|failed",
    "progress_percent": 50
  }
}
```

### task.cancel
Cancel a task.

**Request:**
```json
{
  "method": "task.cancel",
  "params": {
    "task_id": "uuid",
    "reason": "string"
  }
}
```

## Version Negotiation

```
Client: CONNECT with version 1.0.0
Server: 200 OK, supports 1.0.0
```

If incompatible:
```json
{
  "error": {
    "code": 1005,
    "message": "Version mismatch",
    "data": {
      "client_version": "1.0.0",
      "server_version": "2.0.0"
    }
  }
}
```

## Heartbeat

Send every 30 seconds:
```json
{
  "method": "agent.heartbeat",
  "params": {
    "session_id": "uuid"
  }
}
```

Disconnect after 120 seconds without heartbeat.
