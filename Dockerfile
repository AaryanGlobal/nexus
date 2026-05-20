# syntax=docker/dockerfile:1
# Multi-stage Dockerfile for hermes-pi-bridge

#==============================================================================
# Base stage
#==============================================================================
FROM python:3.11-slim as base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

#==============================================================================
# Hermes stage
#==============================================================================
FROM base as hermes

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    httpx \
    pydantic

# Copy Hermes plugin source
COPY packages/core/src /app/packages/core/src
COPY packages/hermes-plugin/src /app/packages/hermes-plugin/src

# Install core package
RUN pip install --no-cache-dir /app/packages/core

# Set environment
ENV PYTHONPATH=/app/packages/core/src:/app/packages/hermes-plugin/src
ENV PORT=8080

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "hermes_pi_bridge.server:create_app", "--host", "0.0.0.0", "--port", "8080"]

#==============================================================================
# pi stage
#==============================================================================
FROM base as pi

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy pi extension source
COPY packages/pi-extension /app/packages/pi-extension

# Install npm dependencies
WORKDIR /app/packages/pi-extension
RUN npm ci
RUN npm run build

WORKDIR /app

# Set environment
ENV PORT=2719

EXPOSE 2719

CMD ["node", "/app/packages/pi-extension/dist/server.js"]

#==============================================================================
# Test stage
#==============================================================================
FROM base as test

# Install Python dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    httpx \
    fastapi

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy everything
COPY packages /app/packages
COPY integration /app/integration

# Install packages
RUN pip install --no-cache-dir /app/packages/core
WORKDIR /app/packages/pi-extension && npm ci

# Run tests
CMD ["bash", "-c", "sleep 5 && /app/integration/test.sh"]