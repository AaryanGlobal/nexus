/**
 * Tests for HermesHttpClient
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { HermesHttpClient } from '../src/transport/client';
import { ErrorCode } from '../src/types';

// Don't mock - we want to test actual implementation
describe('HermesHttpClient integration', () => {
  let client: HermesHttpClient;

  beforeEach(() => {
    client = new HermesHttpClient('http://localhost:9999'); // Non-existent server
  });

  it('getStatus should return error response when server unavailable', async () => {
    const result = await client.getStatus();
    expect(result).toBeDefined();
    expect(result.success).toBe(false);
    expect(result.error).toBeDefined();
  });

  it('delegateTask should return error response when server unavailable', async () => {
    const result = await client.delegateTask({
      task_id: 'test-1',
      title: 'Test',
      description: 'Test task'
    });
    expect(result).toBeDefined();
    expect(result.success).toBe(false);
  });

  it('reportResult should return error response when server unavailable', async () => {
    const result = await client.reportResult({
      task_id: 'test-1',
      status: 'success',
      summary: 'Done'
    });
    expect(result).toBeDefined();
    expect(result.success).toBe(false);
  });

  it('reportReady should not throw when server unavailable', async () => {
    // reportReady returns void, so we just verify it doesn't throw
    await expect(client.reportReady('session-1', 'task-1')).resolves.not.toThrow();
  });

  it('heartbeat should not throw when server unavailable', async () => {
    // heartbeat returns void
    await expect(client.heartbeat('session-1')).resolves.not.toThrow();
  });

  describe('ErrorCode', () => {
    it('should have standard error codes', () => {
      expect(ErrorCode.PARSE_ERROR).toBe(-32700);
      expect(ErrorCode.INVALID_REQUEST).toBe(-32600);
      expect(ErrorCode.METHOD_NOT_FOUND).toBe(-32601);
      expect(ErrorCode.INVALID_PARAMS).toBe(-32602);
      expect(ErrorCode.INTERNAL_ERROR).toBe(-32603);
    });
  });
});