#!/usr/bin/env python3
"""
Example: Using the Hermes-Pi Bridge from Python

This demonstrates how to use the hermes-pi-bridge-core types
and interact with a pi agent from a custom Python script.
"""

from hermes_pi_bridge_core import (
    TaskDelegateRequest,
    TaskResult,
    AgentStatus,
    Priority,
    TaskStatus,
    ErrorCode,
    ProtocolVersion,
)

import httpx
import json
import time


def main():
    # Create a delegation request
    request = TaskDelegateRequest(
        title="Analyze code quality",
        description="Review this Python codebase for potential bugs",
        context={
            "language": "python",
            "repo_url": "https://github.com/example/repo"
        },
        timeout_seconds=300,
        priority=Priority.NORMAL
    )
    
    print(f"Created request: {request.title}")
    print(f"Request dict: {request.to_dict()}")
    
    # Parse a response
    response_data = {
        "task_id": "abc-123",
        "status": "pending",
        "created_at": time.time()
    }
    
    # Create result from dict
    result = TaskResult(
        task_id="abc-123",
        status="success",
        summary="Analysis complete",
        artifacts=[
            {
                "type": "file",
                "path": "/results/report.md",
                "description": "Analysis report"
            }
        ]
    )
    
    print(f"Result: {result.to_dict()}")
    
    # Check protocol version compatibility
    version = ProtocolVersion(1, 0, 0)
    if version.is_compatible(1, 0, 0):
        print("Protocol versions are compatible!")
    
    # Error code example
    print(f"Timeout error: {ErrorCode.TIMEOUT.name} ({ErrorCode.TIMEOUT.value})")
    
    # Agent status
    status = AgentStatus(
        available=True,
        version="1.0.0",
        active_tasks=2,
        max_concurrent=5
    )
    print(f"Agent status: {status.available}")


def http_example():
    """Example HTTP client usage."""
    
    base_url = "http://localhost:8080"  # Hermes bridge server
    headers = {"Authorization": "Bearer your-token"}
    
    with httpx.Client(base_url=base_url, headers=headers) as client:
        # Check pi availability
        response = client.post("/api/v1/agent.status", json={
            "jsonrpc": "2.0",
            "method": "agent.status",
            "params": {"agent_id": "pi-1"},
            "id": 1
        })
        print(f"Status: {response.json()}")
        
        # Delegate a task
        response = client.post("/api/v1/task.delegate", json={
            "jsonrpc": "2.0",
            "method": "task.delegate",
            "params": {
                "title": "Analyze this code",
                "description": "Review main.py for bugs",
                "timeout_seconds": 300
            },
            "id": 2
        })
        print(f"Delegate response: {response.json()}")
        
        # Check task status
        response = client.post("/api/v1/task.status", json={
            "jsonrpc": "2.0",
            "method": "task.status",
            "params": {"task_id": "abc-123"},
            "id": 3
        })
        print(f"Status: {response.json()}")


if __name__ == "__main__":
    main()
    print("\n" + "="*50 + "\n")
    http_example()