# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial TDD implementation with 135+ tests
- Hermes-Pi Bridge for bidirectional task delegation
- Core package with shared types and protocol
- Hermes Python plugin with pi_delegate, pi_status, pi_result tools
- pi TypeScript extension with hermes_delegate, hermes_result tools
- HTTP bridge servers for both agents
- TaskTracker with circuit breaker for failure handling
- Self-seeding installation script
- MIT License
- Contributing Guide
- Code of Conduct
- Security Policy
- GitHub Issue Templates
- GitHub Actions CI/CD pipeline

### Fixed
- TypeScript uuid import issue (used native crypto.randomUUID)
- Python config environment variable handling
- pi extension TypeScript import resolution

### Known Limitations
- No mTLS authentication yet (planned v2.0)
- No audit logging yet (planned v1.1)
- No streaming responses (planned v2.0)

## [1.0.0] - 2026-05-18

### Added
- Initial stable release
- Full protocol specification
- JSON-RPC 2.0 over HTTP
- Bearer token authentication
- CORS support
- Health check endpoints
- Task queue with concurrent limit
- Kanban integration for Hermes

## Versioning

We use [Semantic Versioning](https://semver.org/). Version format: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

## Upgrade Path

### Upgrading from 0.x to 1.0

No known breaking changes in initial release.

## Deprecation Policy

- Deprecated features will be announced 90 days before removal
- Security fixes are never deprecated
- LTS support not currently offered

## Links

- [Protocol Specification](./packages/core/PROTOCOL.md)
- [Installation Guide](./README.md)
- [Contributing](./CONTRIBUTING.md)
- [GitHub Releases](https://github.com/your-org/hermes-pi-bridge/releases)
