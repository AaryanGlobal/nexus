# Makefile for Nexus (PI-Hermes Bridge)

.PHONY: help install test test-core test-hermes test-pi test-integration lint lint-python lint-typescript format build clean publish audit ci venv test-all

# Default target
help:
	@echo "Nexus - PI-Hermes Bridge"
	@echo "======================="
	@echo ""
	@echo "Available targets:"
	@echo "  venv          Create test virtual environment with all dependencies"
	@echo "  install       Install all packages in editable mode"
	@echo "  test          Run all tests (core + hermes-plugin)"
	@echo "  test-core     Run core package tests only"
	@echo "  test-hermes   Run Hermes plugin tests only"
	@echo "  test-pi       Run pi extension tests (Node.js)"
	@echo "  lint          Run all linters"
	@echo "  lint-python   Run Python linter (ruff)"
	@echo "  lint-typescript Run TypeScript linter"
	@echo "  format        Format code"
	@echo "  build         Build packages"
	@echo "  clean         Clean build artifacts"
	@echo "  audit         Run security audits"
	@echo "  ci            Full CI simulation"

# Virtual environment setup
VENV := .test-venv
PYTHON := python3.11

venv:
	@echo "Creating test virtual environment..."
	@uv venv $(VENV) --python $(PYTHON)
	@uv pip install --python $(VENV)/bin/python \
		pytest pytest-asyncio pytest-cov websockets httpx pydantic fastapi ruff
	@uv pip install --python $(VENV)/bin/python -e packages/core -e packages/hermes-plugin
	@echo "Done! Activate with: source $(VENV)/bin/activate"

# Installation
install:
	@echo "Installing packages in development mode..."
	@uv pip install --python .test-venv/bin/python -e packages/core -e packages/hermes-plugin

# Testing
test: test-core test-hermes
	@echo ""
	@echo "All Python tests passed!"

test-core:
	@echo "Running core package tests..."
	@. .test-venv/bin/activate && pytest packages/core/tests -q --tb=short

test-hermes:
	@echo "Running Hermes plugin tests..."
	@. .test-venv/bin/activate && pytest packages/hermes-plugin/tests -q --tb=short

test-pi:
	@echo "Running pi extension tests..."
	@cd packages/pi-extension && npm test -- --run

test-all: test test-pi
	@echo ""
	@echo "All tests passed!"

# Linting
lint: lint-python lint-typescript
	@echo "All linting passed!"

lint-python:
	@echo "Linting Python code..."
	@. .lint-venv/bin/activate && ruff check packages/core/src packages/hermes-plugin/src
	@echo "Python linting passed!"

lint-typescript:
	@echo "Linting TypeScript code..."
	@cd packages/pi-extension && npm run lint
	@echo "TypeScript linting passed!"

# Formatting
format:
	@echo "Formatting code..."
	@. .lint-venv/bin/activate && ruff format packages/core/src packages/hermes-plugin/src
	@cd packages/pi-extension && npx prettier --write src/**/*.ts || true

# Building
build: build-python build-typescript

build-python:
	@echo "Building Python packages..."
	@cd packages/core && uv build
	@cd packages/hermes-plugin && uv build

build-typescript:
	@echo "Building TypeScript package..."
	@cd packages/pi-extension && npm run build

# Cleaning
clean:
	@echo "Cleaning build artifacts..."
	@rm -rf packages/*/build
	@rm -rf packages/*/*.egg-info
	@rm -rf packages/pi-extension/dist
	@rm -rf .ruff_cache
	@rm -rf htmlcov
	@rm -rf .coverage
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

# Publishing
publish:
	@echo "Publishing packages..."
	@cd packages/core && uv publish
	@cd packages/hermes-plugin && uv publish
	@cd packages/pi-extension && npm publish --access public

# Security audit
audit:
	@echo "Running security audits..."
	@cd packages/pi-extension && npm audit --audit-level=high || true

# Full CI simulation
ci: lint test audit
	@echo ""
	@echo "CI pipeline passed!"

# Docker
docker-build:
	docker build -t nexus-bridge .

docker-run:
	docker run -it nexus-bridge