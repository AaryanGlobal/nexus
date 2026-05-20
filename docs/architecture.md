# Architecture

This document describes the internal architecture of the Hermes-Pi Bridge.

## Overview

The Hermes-Pi Bridge enables bidirectional task delegation between Hermes and pi agents. It follows a hub-and-spoke model where each agent runs a local HTTP server that exposes a JSON-RPC 2.0 API.

## Components

```
┌────────────────────────────────────────────────────────────────────┐
│                     HERMES-PI BRIDGE STACK                          │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────┐         ┌─────────────────────┐          │
│  │   HERMES SIDE       │         │   PI SIDE            │          │
│  │                     │         │                     │          │
│  │  ┌───────────────┐  │         │  ┌───────────────┐  │          │
│  │  │ hermes-plugin │  │         │  │ pi-extension  │  │          │
│  │  │               │  │         │  │               │  │          │
│  │  │ • pi_delegate │  │         │  │ • hermes_del  │  │          │
│  │  │ • pi_status   │  │         │  │ • hermes_result│  │          │
│  │  │ • pi_result   │  │         │  │               │  │          │
│  │  └───────────────┘  │         │  └───────────────┘  │          │
│  │         │           │         │         │           │          │
│  │         ▼           │         │         ▼           │          │
│  │  ┌───────────────┐  │         │  ┌───────────────┐  │          │
│  │  │   server.py   │  │◀───────▶│  │   server.ts   │  │          │
│  │  │   FastAPI     │  │  HTTP   │  │   Node.js     │  │          │
│  │  │   :8080       │  │  JSON   │  │   :2719       │  │          │
│  │  └───────────────┘  │         │  └───────────────┘  │          │
│  │         │           │         │         │           │          │
│  │         ▼           │         │         ▼           │          │
│  │  ┌───────────────┐  │         │  ┌───────────────┐  │          │
│  │  │ TaskTracker   │  │         │  │ TaskQueue     │  │          │
│  │  │ • Kanban      │  │         │  │ • Concurrent  │  │          │
│  │  │ • Failures    │  │         │  │ • Priority    │  │          │
│  │  └───────────────┘  │         │  └───────────────┘  │          │
│  └─────────────────────┘         └─────────────────────┘          │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

## Packages

### Core (`packages/core`)

Shared types and protocol definitions:

- `types.py` - Pydantic models for all protocol messages
- `PROTOCOL.md` - Full API specification

**Dependencies**: `pydantic>=2.0.0`

### Hermes Plugin (`packages/hermes-plugin`)

Python plugin for Hermes agent:

- `tools/` - MCP tools (pi_delegate, pi_status, pi_result)
- `server.py` - FastAPI HTTP server
- `kanban.py` - Hermes Kanban integration

**Dependencies**: 
- `hermes-agent>=0.14.0`
- `httpx>=0.28.0`
- `hermes-pi-bridge-core`

### pi Extension (`packages/pi-extension`)

TypeScript extension for pi:

- `tools.ts` - Tool definitions
- `server.ts` - Node.js HTTP server
- `transport/client.ts` - HTTP client

**Dependencies**: None (pure Node.js)

## Protocol

All communication uses JSON-RPC 2.0 over HTTP:

### Endpoints

**pi HTTP Server (port 2719)**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/task.delegate` | Receive task from Hermes |
| POST | `/api/v1/task.result` | Receive result from tools |
| POST | `/api/v1/task.status` | Get task status |
| POST | `/api/v1/task.cancel` | Cancel task |
| POST | `/api/v1/agent.status` | Health check |
| GET | `/api/v1/health` | Health check |

**Hermes HTTP Server (port 8080)**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/task.result` | Receive result from pi |
| POST | `/api/v1/task.status` | Get task status |
| POST | `/api/v1/task.cancel` | Cancel task |
| POST | `/api/v1/agent.status` | Health check |
| POST | `/api/v1/agent.ready` | pi ready notification |
| GET | `/api/v1/health` | Health check |

### Message Types

See `packages/core/PROTOCOL.md` for full specification.

## Task Lifecycle

```
1. Delegation Request
   Hermes → pi_delegate → HTTP POST /task.delegate
   │
2. Task Tracking
   Hermes → Kanban created with pending status
   │
3. Task Execution
   pi receives task, executes, tracks progress
   │
4. Result Submission
   pi → HTTP POST /task.result (to Hermes server)
   │
5. Result Processing
   Hermes → Kanban updated, result stored
   │
6. Result Retrieval
   Hermes → pi_result tool → result returned
```

## Error Handling

### Circuit Breaker

The `TaskTracker` in Hermes tracks consecutive failures:

- After 3 consecutive failures, task is marked as "blocked"
- Success resets failure counter
- Configurable via `max_failures` setting

### Error Codes

| Range | Category |
|-------|----------|
| -32768 to -32000 | JSON-RPC 2.0 reserved |
| -32099 to -32000 | Server-defined errors |
| 1000-1999 | Bridge-specific errors |

See `packages/core/src/types.py` for full error code list.

## Configuration

### Hermes (`~/.hermes/config.yaml`)

```yaml
plugins:
  - hermes-pi-bridge

hermes_pi_bridge:
  pi_url: "http://localhost:2719"
  auth_token: ""  # Optional
  max_concurrent: 2
  timeout_seconds: 300
```

### pi (`~/.pi/agent/settings.json`)

```json
{
  "packages": ["hermes-pi-bridge"],
  "hermesBridge": {
    "hermesUrl": "http://localhost:8080",
    "authToken": ""
  }
}
```

## Security

- **Authentication**: Bearer token in `Authorization` header
- **Input Validation**: Pydantic models validate all inputs
- **Rate Limiting**: 10 requests/second per session (configurable)
- **CORS**: Enabled for localhost development

## Future Enhancements

See [CHANGELOG.md](../CHANGELOG.md) for planned features.