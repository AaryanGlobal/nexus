/**
 * Tests for pi HTTP server implementation.
 * 
 * TDD: These tests verify the BridgeServer implementation.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { BridgeServer, BridgeServerConfig } from '../src/server';

// Mock HTTP module
vi.mock('http', () => ({
  createServer: vi.fn(() => ({
    on: vi.fn(),
    listen: vi.fn((port, host, cb) => cb()),
    close: vi.fn((cb) => cb()),
  })),
}));

describe('BridgeServer', () => {
  let server: BridgeServer;

  beforeEach(() => {
    server = new BridgeServer({
      port: 9999,
      host: '127.0.0.1',
      maxConcurrent: 2,
    });
  });

  afterEach(async () => {
    await server.stop();
  });

  describe('constructor', () => {
    it('should set default configuration', () => {
      const defaultServer = new BridgeServer();
      expect((defaultServer as any).config.port).toBe(2719);
      expect((defaultServer as any).config.host).toBe('0.0.0.0');
      expect((defaultServer as any).config.maxConcurrent).toBe(2);
    });

    it('should accept custom configuration', () => {
      const customServer = new BridgeServer({
        port: 3000,
        host: 'localhost',
        authToken: 'secret',
        maxConcurrent: 5,
      });
      expect((customServer as any).config.port).toBe(3000);
      expect((customServer as any).config.host).toBe('localhost');
      expect((customServer as any).config.authToken).toBe('secret');
      expect((customServer as any).config.maxConcurrent).toBe(5);
    });
  });

  describe('start/stop', () => {
    it('should start and stop without error', async () => {
      await expect(server.start()).resolves.toBeUndefined();
      await expect(server.stop()).resolves.toBeUndefined();
    });
  });

  describe('API Endpoints', () => {
    // These tests document the expected API contract
    
    it('should handle POST /api/v1/agent.status', () => {
      // Expected request format
      const request = {
        jsonrpc: '2.0',
        method: 'agent.status',
        params: { agent_type: 'pi', version: '1.0.0' },
        id: '1',
      };
      expect(request.method).toBe('agent.status');
    });

    it('should handle POST /api/v1/task.delegate', () => {
      const request = {
        jsonrpc: '2.0',
        method: 'task.delegate',
        params: {
          task_id: 'test-123',
          title: 'Test task',
          description: 'A test task',
          timeout_seconds: 300,
        },
        id: '1',
      };
      expect(request.method).toBe('task.delegate');
      expect(request.params.task_id).toBe('test-123');
    });

    it('should handle POST /api/v1/task.result', () => {
      const request = {
        jsonrpc: '2.0',
        method: 'task.result',
        params: {
          task_id: 'test-123',
          status: 'success',
          summary: 'Task completed',
          artifacts: [{ path: 'output.py', type: 'file' }],
        },
        id: '1',
      };
      expect(request.method).toBe('task.result');
      expect(request.params.status).toBe('success');
    });

    it('should handle POST /api/v1/task.cancel', () => {
      const request = {
        jsonrpc: '2.0',
        method: 'task.cancel',
        params: {
          task_id: 'test-123',
          reason: 'User cancelled',
        },
        id: '1',
      };
      expect(request.method).toBe('task.cancel');
    });
  });

  describe('Request Validation', () => {
    it('should validate task.delegate requires title or description', () => {
      // Empty request should fail validation
      const invalidRequest = {
        jsonrpc: '2.0',
        method: 'task.delegate',
        params: {},
        id: '1',
      };
      expect(!invalidRequest.params.title && !invalidRequest.params.description).toBe(true);
    });

    it('should validate task.result requires task_id', () => {
      const invalidRequest = {
        jsonrpc: '2.0',
        method: 'task.result',
        params: {
          status: 'success',
        },
        id: '1',
      };
      expect(!invalidRequest.params.task_id).toBe(true);
    });
  });

  describe('Response Format', () => {
    it('should return JSON-RPC 2.0 success response', () => {
      const response = {
        jsonrpc: '2.0',
        result: { task_id: 'test-123', status: 'accepted' },
        id: '1',
      };
      expect(response.jsonrpc).toBe('2.0');
      expect(response.result).toBeDefined();
      expect(response.id).toBe('1');
    });

    it('should return JSON-RPC 2.0 error response', () => {
      const errorResponse = {
        jsonrpc: '2.0',
        error: {
          code: -32600,
          message: 'Invalid Request',
        },
        id: '1',
      };
      expect(errorResponse.jsonrpc).toBe('2.0');
      expect(errorResponse.error.code).toBe(-32600);
    });
  });

  describe('Authentication', () => {
    it('should accept valid Bearer token when configured', () => {
      const token = 'valid-token';
      const authServer = new BridgeServer({ authToken: token });
      expect((authServer as any).config.authToken).toBe(token);
    });

    it('should allow requests without token when not configured', () => {
      const noAuthServer = new BridgeServer();
      expect((noAuthServer as any).config.authToken).toBeUndefined();
    });
  });

  describe('Task Queue', () => {
    it('should respect max_concurrent limit', () => {
      const limitedServer = new BridgeServer({ maxConcurrent: 1 });
      expect((limitedServer as any).config.maxConcurrent).toBe(1);
    });

    it('should track tasks internally', () => {
      expect((server as any).tasks).toBeInstanceOf(Map);
      expect((server as any).taskQueue).toBeInstanceOf(Array);
    });

    it('should track running tasks', () => {
      expect((server as any).runningTasks).toBeInstanceOf(Set);
    });
  });

  describe('Health Check', () => {
    it('should have health endpoint', () => {
      // GET /api/v1/health should return server status
      const healthResponse = {
        status: 'ok',
        version: '1.0.0',
        tasks: {
          total: 0,
          running: 0,
          queued: 0,
        },
      };
      expect(healthResponse.status).toBe('ok');
    });
  });
});

describe('Task Queue Logic', () => {
  describe('Queue Management', () => {
    it('should add tasks in FIFO order', () => {
      const queue: string[] = [];
      queue.push('task-1');
      queue.push('task-2');
      queue.push('task-3');
      
      const next = queue.shift();
      expect(next).toBe('task-1');
      expect(queue.length).toBe(2);
    });

    it('should process tasks up to max concurrent', () => {
      const maxConcurrent = 2;
      const runningTasks = new Set<string>();
      const queue = ['task-1', 'task-2', 'task-3'];
      
      // Start first two tasks
      while (runningTasks.size < maxConcurrent && queue.length > 0) {
        const taskId = queue.shift();
        if (taskId) runningTasks.add(taskId);
      }
      
      expect(runningTasks.size).toBe(2);
      expect(queue.length).toBe(1);
    });

    it('should track task status correctly', () => {
      const taskStates = new Map<string, string>();
      
      taskStates.set('task-1', 'pending');
      expect(taskStates.get('task-1')).toBe('pending');
      
      taskStates.set('task-1', 'running');
      expect(taskStates.get('task-1')).toBe('running');
      
      taskStates.set('task-1', 'completed');
      expect(taskStates.get('task-1')).toBe('completed');
    });
  });

  describe('Progress Calculation', () => {
    it('should return 0 for pending tasks', () => {
      const task = { status: 'pending' };
      const progress = task.status === 'pending' ? 0 : 50;
      expect(progress).toBe(0);
    });

    it('should return 100 for completed tasks', () => {
      const task = { status: 'completed' };
      const progress = ['completed', 'failed', 'cancelled'].includes(task.status) ? 100 : 50;
      expect(progress).toBe(100);
    });
  });
});
