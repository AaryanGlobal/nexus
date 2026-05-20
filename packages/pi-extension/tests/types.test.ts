/**
 * Tests for pi extension types.
 * 
 * TDD: These tests verify type compatibility between Python and TypeScript.
 */

import { describe, it, expect } from 'vitest';
import {
  AgentType,
  TaskStatus,
  Priority,
  ErrorCode,
  PROTOCOL_VERSION,
  TaskDelegateRequest,
  TaskResultRequest,
} from '../src/types';

describe('Type Definitions', () => {
  describe('AgentType', () => {
    it('should have hermes and pi values', () => {
      expect(AgentType.HERMES).toBe('hermes');
      expect(AgentType.PI).toBe('pi');
    });
  });

  describe('TaskStatus', () => {
    it('should have all expected status values', () => {
      expect(TaskStatus.PENDING).toBe('pending');
      expect(TaskStatus.RUNNING).toBe('running');
      expect(TaskStatus.SUCCESS).toBe('success');
      expect(TaskStatus.PARTIAL).toBe('partial');
      expect(TaskStatus.FAILED).toBe('failed');
      expect(TaskStatus.BLOCKED).toBe('blocked');
      expect(TaskStatus.CANCELLED).toBe('cancelled');
    });
  });

  describe('Priority', () => {
    it('should have low, normal, high values', () => {
      expect(Priority.LOW).toBe('low');
      expect(Priority.NORMAL).toBe('normal');
      expect(Priority.HIGH).toBe('high');
    });
  });

  describe('ErrorCode', () => {
    it('should have JSON-RPC 2.0 error codes', () => {
      expect(ErrorCode.PARSE_ERROR).toBe(-32700);
      expect(ErrorCode.INVALID_REQUEST).toBe(-32600);
      expect(ErrorCode.METHOD_NOT_FOUND).toBe(-32601);
      expect(ErrorCode.INVALID_PARAMS).toBe(-32602);
      expect(ErrorCode.INTERNAL_ERROR).toBe(-32603);
    });

    it('should have bridge-specific error codes in 1000-1999 range', () => {
      expect(ErrorCode.AUTH_ERROR).toBe(1000);
      expect(ErrorCode.SESSION_NOT_FOUND).toBe(1001);
      expect(ErrorCode.TASK_NOT_FOUND).toBe(1002);
      expect(ErrorCode.TIMEOUT).toBe(1003);
      expect(ErrorCode.CAPACITY_EXCEEDED).toBe(1004);
      expect(ErrorCode.VERSION_MISMATCH).toBe(1005);
    });
  });

  describe('ProtocolVersion', () => {
    it('should export protocol version string', () => {
      expect(PROTOCOL_VERSION).toBe('1.0.0');
    });
  });

  describe('TaskDelegateRequest', () => {
    it('should be a valid interface', () => {
      const request: TaskDelegateRequest = {
        title: 'Test task',
        description: 'A test task description',
        timeout_seconds: 300,
        priority: 'normal',
      };

      expect(request.title).toBe('Test task');
      expect(request.timeout_seconds).toBe(300);
    });

    it('should allow optional fields', () => {
      const request: TaskDelegateRequest = {
        title: 'Minimal task',
        description: 'A minimal task',
      };

      expect(request.timeout_seconds).toBeUndefined();
      expect(request.priority).toBeUndefined();
    });

    it('should allow context with workspace and files', () => {
      const request: TaskDelegateRequest = {
        title: 'Task with context',
        description: 'Task with files',
        context: {
          workspace: '/project',
          files: ['a.py', 'b.py'],
          checkpoint_hash: 'sha256:abc123',
        },
      };

      expect(request.context?.workspace).toBe('/project');
      expect(request.context?.files?.length).toBe(2);
    });
  });

  describe('TaskResultRequest', () => {
    it('should be a valid interface for success', () => {
      const result: TaskResultRequest = {
        task_id: 'task-123',
        status: 'success',
        summary: 'Completed successfully',
        artifacts: [
          { path: 'output.py', type: 'file', checksum: 'sha256:xyz' },
        ],
      };

      expect(result.status).toBe('success');
      expect(result.artifacts?.length).toBe(1);
    });

    it('should be a valid interface for failure', () => {
      const result: TaskResultRequest = {
        task_id: 'task-123',
        status: 'failed',
        summary: 'Task failed',
        errors: ['Error 1', 'Error 2'],
      };

      expect(result.status).toBe('failed');
      expect(result.errors?.length).toBe(2);
    });

    it('should support all status values', () => {
      const statuses: TaskResultRequest['status'][] = [
        'success',
        'partial',
        'failed',
        'blocked',
      ];

      statuses.forEach(status => {
        const result: TaskResultRequest = {
          task_id: 'test',
          status,
          summary: 'test',
        };
        expect(result.status).toBe(status);
      });
    });
  });
});
