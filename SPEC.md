# Hermes-Pi Bridge

**Version:** 1.0.0
**Status:** Stable
**Repository:** Single monorepo that seeds to both Hermes and pi agents

## Overview

Hermes-Pi Bridge enables bidirectional task delegation between Hermes and pi agents.

```
┌────────────────────────────────────────────────────────────────────┐
│                     MONOREPO STRUCTURE                             │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   hermes-pi-bridge/           ← Git clone here                     │
│   ├── packages/                                                    │
│   │   ├── core/               ← Shared types & protocol           │
│   │   ├── hermes-plugin/      ← Hermes Python plugin               │
│   │   └── pi-extension/       ← pi TypeScript extension           │
│   ├── scripts/                                                    │
│   │   └── seed.sh             ← Self-installs to both agents       │
│   ├── integration/                                                │
│   │   └── test.sh            ← Integration test runner            │
│   ├── SPEC.md                 ← This file (source of truth)       │
│   └── README.md                                                   │
│                                                                     │
│   After seeding:                                                  │
│   ~/.hermes/plugins/hermes-pi-bridge/  ← Hermes plugin            │
│   ~/.pi/agent/npm/hermes-pi-bridge/    ← pi extension            │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-org/hermes-pi-bridge.git
cd hermes-pi-bridge

# 2. Seed to both agents
./scripts/seed.sh

# 3. Configure (edit auto-generated config)
nano ~/.hermes/config.yaml
nano ~/.pi/agent/settings.json
```

## Protocol Version

| Version | Hermes | pi | Status |
|---------|--------|----|----|
| 1.0.x   | 0.14.x | 0.75.x | ✅ Current |

## Installation Methods

### Option A: Git Clone + Seed (Recommended)
```bash
git clone https://github.com/your-org/hermes-pi-bridge.git
cd hermes-pi-bridge
./scripts/seed.sh
```

### Option B: npm (pi only)
```bash
pi install npm:hermes-pi-bridge
```

### Option C: pip (Hermes only)
```bash
pip install hermes-pi-bridge
```

## Architecture

### Hermes Plugin (`packages/hermes-plugin/`)
- **Location after install:** `~/.hermes/plugins/hermes-pi-bridge/`
- **Entry point:** `hermes_pi_bridge:register`
- **Tools:**
  - `pi_delegate` - Send task to pi
  - `pi_status` - Check pi availability
  - `pi_result` - Receive pi results

### pi Extension (`packages/pi-extension/`)
- **Location after install:** `~/.pi/agent/npm/hermes-pi-bridge/`
- **Entry point:** `index.ts`
- **Tools:**
  - `hermes_delegate` - Send task to Hermes
  - `hermes_result` - Report task result

### Shared Core (`packages/core/`)
- **Types:** Python dataclasses + TypeScript interfaces
- **Protocol:** JSON-RPC 2.0 over HTTP
- **Validators:** Request/response validation

## Configuration

### Hermes (`~/.hermes/config.yaml`)
```yaml
plugins:
  - hermes-pi-bridge

hermes_pi_bridge:
  # pi HTTP server URL
  pi_url: "http://localhost:2719"
  # Authentication token
  auth_token: ""
  # Max concurrent tasks
  max_concurrent: 2
  # Default timeout (seconds)
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

## API Reference

See `packages/core/PROTOCOL.md` for full API specification.

### Endpoints

| Method | Direction | Description |
|--------|-----------|-------------|
| `agent.status` | Both | Check agent availability |
| `task.delegate` | Both | Submit a task |
| `task.result` | Both | Report task completion |
| `task.status` | Both | Get task status |
| `task.cancel` | Both | Cancel a running task |
| `agent.heartbeat` | Both | Keep-alive |

## Development

### Prerequisites
- Python 3.11+
- Node.js 18+
- Hermes 0.14+
- pi 0.75+

### Local Development
```bash
# Install dependencies
pip install -e packages/core
pip install -e packages/hermes-plugin
npm install packages/pi-extension

# Run seed script (creates symlinks)
./scripts/seed.sh --dev

# Run integration tests
./integration/test.sh
```

## Change Log

### 1.0.0 (2026-05-18)
- Initial stable release
- Basic delegation and result reporting
- Hermes Kanban integration
