/**
 * NHIL Autonomous Loop Tests - Integration tests (no mocking)
 */

import { describe, it, expect } from 'vitest';
import { HermesHttpClient } from '../src/transport/client';
import { ErrorCode } from '../src/types';

describe('NHIL: Client Methods Exist', () => {
  const client = new HermesHttpClient('http://localhost:9999', '', 5000);

  it('heartbeat method exists', () => {
    expect(typeof client.heartbeat).toBe('function');
  });

  it('reportReady method exists', () => {
    expect(typeof client.reportReady).toBe('function');
  });

  it('delegateTask method exists', () => {
    expect(typeof client.delegateTask).toBe('function');
  });

  it('reportResult method exists', () => {
    expect(typeof client.reportResult).toBe('function');
  });

  it('getStatus method exists', () => {
    expect(typeof client.getStatus).toBe('function');
  });
});

describe('NHIL: Error Handling (server unavailable)', () => {
  const client = new HermesHttpClient('http://localhost:9999', '', 1000);

  it('getStatus returns error response', async () => {
    const result = await client.getStatus();
    expect(result).toBeDefined();
    expect(result.success).toBe(false);
    expect(result.error).toBeDefined();
  });

  it('delegateTask returns error response', async () => {
    const result = await client.delegateTask({
      task_id: 'test-1',
      title: 'Test',
      description: 'Test task'
    });
    expect(result).toBeDefined();
    expect(result.success).toBe(false);
  });

  it('reportResult returns error response', async () => {
    const result = await client.reportResult({
      task_id: 'test-1',
      status: 'success',
      summary: 'Done'
    });
    expect(result).toBeDefined();
    expect(result.success).toBe(false);
  });

  it('heartbeat does not throw', async () => {
    await expect(client.heartbeat('session-1')).resolves.not.toThrow();
  });

  it('reportReady does not throw', async () => {
    await expect(client.reportReady('session-1', 'task-1')).resolves.not.toThrow();
  });
});

describe('NHIL: Error Codes', () => {
  it('has all required error codes', () => {
    expect(ErrorCode.PARSE_ERROR).toBe(-32700);
    expect(ErrorCode.INVALID_REQUEST).toBe(-32600);
    expect(ErrorCode.METHOD_NOT_FOUND).toBe(-32601);
    expect(ErrorCode.INVALID_PARAMS).toBe(-32602);
    expect(ErrorCode.INTERNAL_ERROR).toBe(-32603);
    expect(ErrorCode.TIMEOUT).toBe(1003);
    expect(ErrorCode.TASK_NOT_FOUND).toBe(1002);
  });
});
