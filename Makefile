# Makefile for hermes-pi-bridge

.PHONY: help install test lint format clean build publish test-all

# Default target
help:
	@echo "Hermes-Pi Bridge - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install      Install packages in dev mode"
	@echo "  test         Run all tests"
	@echo "  test-core    Run core package tests"
	@echo "  test-hermes  Run Hermes plugin tests"
	@echo "  test-pi      Run pi extension tests"
	@echo "  test-integration  Run integration tests"
	@echo "  lint         Run linters"
	@echo "  lint-python  Run Python linter"
	@echo "  lint-typescript  Run TypeScript linter"
	@echo "  format       Format code"
	@echo "  build        Build packages"
	@echo "  build-python Build Python packages"
	@echo "  build-typescript Build TypeScript package"
	@echo "  clean        Clean build artifacts"
	@echo "  publish      Publish packages to PyPI and npm"
	@echo "  audit        Run security audits"

# Installation
install:
	@echo "Installing hermes-pi-bridge in development mode..."
	./scripts/seed.sh --dev

# Testing
test: test-core test-hermes test-pi test-integration

test-core:
	@echo "Running core package tests..."
	cd packages/core && pytest tests/ -v

test-hermes:
	@echo "Running Hermes plugin tests..."
	cd packages/hermes-plugin && PYTHONPATH=src pytest tests/ -v

test-pi:
	@echo "Running pi extension tests..."
	cd packages/pi-extension && npm test

test-integration:
	@echo "Running integration tests..."
	./integration/test.sh

# Linting
lint: lint-python lint-typescript

lint-python:
	@echo "Linting Python code..."
	ruff check packages/core/src packages/hermes-plugin/src

lint-typescript:
	@echo "Linting TypeScript code..."
	cd packages/pi-extension && npm run lint || echo "ESLint not configured"

# Formatting
format:
	@echo "Formatting code..."
	ruff format packages/core/src packages/hermes-plugin/src
	cd packages/pi-extension && npx prettier --write src/**/*.ts || true

# Building
build: build-python build-typescript

build-python:
	@echo "Building Python packages..."
	python -m build packages/core
	python -m build packages/hermes-plugin

build-typescript:
	@echo "Building TypeScript package..."
	cd packages/pi-extension && npm run build

# Cleaning
clean:
	@echo "Cleaning build artifacts..."
	rm -rf packages/*/build
	rm -rf packages/*/*.egg-info
	rm -rf packages/pi-extension/dist
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true

# Publishing
publish:
	@echo "Publishing packages..."
	python -m twine upload packages/core/dist/*
	python -m twine upload packages/hermes-plugin/dist/*
	cd packages/pi-extension && npm publish --access public

# Security audit
audit:
	@echo "Running security audits..."
	-pip-audit
	cd packages/pi-extension && npm audit

# Full CI simulation
ci: lint test audit

# Docker
docker-build:
	docker build -t hermes-pi-bridge .

docker-run:
	docker run -it hermes-pi-bridge

# Seed script
seed:
	./scripts/seed.sh

seed-check:
	./scripts/seed.sh --check

seed-uninstall:
	./scripts/seed.sh --uninstall