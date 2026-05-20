# Contributing to Hermes-Pi Bridge

Hey, we're glad you're interested in contributing!

This project is young, and there's plenty of room for improvement. Whether you spot a bug, have an idea for a feature, or just want to clean something up—your help is welcome.

## Code of Conduct

Before anything else, please read our [Code of Conduct](./CODE_OF_CONDUCT.md). Basically: be excellent to each other.

## Prerequisites

You'll need:
- Python 3.11+
- Node.js 18+
- Hermes 0.14+ (if testing Hermes integration)
- pi 0.75+ (if testing pi integration)

## Getting Started

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR_USERNAME/hermes-pi-bridge.git
cd hermes-pi-bridge
```

### 2. Install in Dev Mode

```bash
./scripts/seed.sh --dev
```

This symlinks the packages to your agents instead of copying files. Changes to the source show up immediately.

### 3. Run Tests

```bash
# Everything
./integration/test.sh

# Just Python
cd packages/hermes-plugin && pytest tests/ -v

# Just TypeScript
cd packages/pi-extension && npx vitest run
```

## Making Changes

### Branches

```bash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/something-broken
```

### Code Standards

**Python:**
- We use `ruff` for linting. Run it before committing:
  ```bash
  ruff check packages/core/src packages/hermes-plugin/src
  ```
- Format with: `ruff format`

**TypeScript:**
- Run the linter: `cd packages/pi-extension && npm run lint`
- Format with Prettier (we have a config for that)

**Commits:**
We follow [Conventional Commits](https://www.conventionalcommits.org/). Quick version:

```
feat(delegation): add timeout handling
fix(server): handle connection drops gracefully
docs(readme): clarify installation steps
test(bridge): add integration tests for error cases
```

### Testing

Every feature needs tests. Every bug fix needs a test that would have caught it.

```bash
# Python
cd packages/hermes-plugin
PYTHONPATH=src pytest tests/ -v

# TypeScript
cd packages/pi-extension
npx vitest run
```

All tests must pass before merging.

## Submitting Changes

1. **Push** your branch to your fork
2. **Open a PR** against `main`
3. **Fill out the PR template** (it appears automatically)
4. **Wait for review**—we'll get back to you within a few days

### PR Checklist

- [ ] Tests pass locally
- [ ] Linting passes (`ruff check` and `npm run lint`)
- [ ] Commit messages follow the format
- [ ] Docs updated if needed
- [ ] No breaking changes (or clearly documented)

## Project Layout

```
hermes-pi-bridge/
├── packages/
│   ├── core/              # Shared types both agents use
│   ├── hermes-plugin/     # Python plugin for Hermes
│   └── pi-extension/      # TypeScript extension for pi
├── scripts/
│   └── seed.sh            # Installs everything
├── integration/
│   └── test.sh            # Full integration tests
└── docs/                  # Architecture & API docs
```

## Found a Bug?

Open an issue using the [Bug Report template](./.github/ISSUE_TEMPLATE/bug_report.yml). Include:
- Hermes and pi versions
- What you tried to do
- What happened instead
- Relevant logs

## Have an Idea?

Open an issue using the [Feature Request template](./.github/ISSUE_TEMPLATE/feature_request.yml). Tell us:
- What problem you're solving
- How you envision it working
- Any alternatives you've considered

## Questions?

Open a discussion in GitHub Issues. For bigger changes, it's worth opening an issue first to chat about the approach before writing code.

## License

By contributing, you agree your changes will be licensed under the MIT License.