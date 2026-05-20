/**
 * Example: Using the Hermes-Pi Bridge from TypeScript
 * 
 * This demonstrates how to use the bridge types and interact
 * with a Hermes agent from a custom TypeScript/Node.js script.
 */

import {
  PROTOCOL_VERSION,
  TaskDelegateRequest,
  TaskResult,
  AgentStatus,
  Priority,
  TaskStatus,
  ErrorCode,
  type Artifact,
} from '../packages/pi-extension/src/types';

async function main() {
  console.log(`Protocol version: ${PROTOCOL_VERSION}`);

  // Create a delegation request
  const request: TaskDelegateRequest = {
    title: 'Analyze code quality',
    description: 'Review this codebase for potential bugs',
    context: {
      language: 'typescript',
      files: ['src/**/*.ts'],
    },
    timeout_seconds: 300,
    priority: Priority.NORMAL,
  };

  console.log('Created request:', request);

  // Create a result
  const result: TaskResult = {
    task_id: 'abc-123',
    status: 'success',
    summary: 'Analysis complete. Found 3 issues.',
    artifacts: [
      {
        type: 'file',
        path: '/results/report.md',
        description: 'Analysis report',
      },
    ] as Artifact[],
    duration_seconds: 45.5,
  };

  console.log('Result:', result);

  // Check status
  const status: AgentStatus = {
    available: true,
    version: '1.0.0',
    active_tasks: 2,
    max_concurrent: 5,
    timestamp: Date.now(),
  };

  console.log('Agent available:', status.available);
}

async function httpExample() {
  /** Example HTTP client usage */
  const baseUrl = 'http://localhost:8080'; // Hermes bridge server
  const token = 'your-token';

  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };

  // Check pi availability
  const statusResponse = await fetch(`${baseUrl}/api/v1/agent.status`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      jsonrpc: '2.0',
      method: 'agent.status',
      params: { agent_id: 'pi-1' },
      id: 1,
    }),
  });

  const statusData = await statusResponse.json();
  console.log('Status:', statusData);

  // Delegate a task
  const delegateResponse = await fetch(`${baseUrl}/api/v1/task.delegate`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      jsonrpc: '2.0',
      method: 'task.delegate',
      params: {
        title: 'Analyze this code',
        description: 'Review main.ts for bugs',
        timeout_seconds: 300,
      },
      id: 2,
    }),
  });

  const delegateData = await delegateResponse.json();
  console.log('Delegate response:', delegateData);

  // Check task status
  const taskStatusResponse = await fetch(`${baseUrl}/api/v1/task.status`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      jsonrpc: '2.0',
      method: 'task.status',
      params: { task_id: 'abc-123' },
      id: 3,
    }),
  });

  const taskStatusData = await taskStatusResponse.json();
  console.log('Task status:', taskStatusData);
}

// Run examples
main().catch(console.error);
httpExample().catch(console.error);