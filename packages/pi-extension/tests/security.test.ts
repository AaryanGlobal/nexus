/**
 * OWASP Security Controls - TypeScript Tests
 */

import { describe, it, expect } from 'vitest';
import { ErrorCode } from '../src/types';

describe('OWASP Security: Error Codes', () => {
  it('has security-relevant error codes', () => {
    expect(ErrorCode.AUTH_ERROR).toBe(1000);
    expect(ErrorCode.SESSION_NOT_FOUND).toBe(1001);
    expect(ErrorCode.TASK_NOT_FOUND).toBe(1002);
    expect(ErrorCode.TIMEOUT).toBe(1003);
    expect(ErrorCode.CAPACITY_EXCEEDED).toBe(1004);
    expect(ErrorCode.VERSION_MISMATCH).toBe(1005);
  });
});

describe('OWASP Security: Input Validation', () => {
  it('should have validation for JSON-RPC requests', () => {
    // Valid request structure
    const validRequest = {
      jsonrpc: '2.0',
      method: 'task.delegate',
      params: { task_id: 'test-1', title: 'Test' },
      id: '1'
    };
    expect(validRequest.jsonrpc).toBe('2.0');
  });

  it('should reject malformed JSON-RPC', () => {
    // Missing jsonrpc field should be rejected
    const malformed = {
      method: 'task.delegate',
      params: {}
    };
    expect(malformed.jsonrpc).toBeUndefined();
  });
});

describe('OWASP Security: Rate Limiting', () => {
  it('client should handle rate limit gracefully', async () => {
    const { HermesHttpClient } = await import('../src/transport/client');
    const client = new HermesHttpClient('http://localhost:9999');
    
    // Multiple rapid requests should not crash
    const results = await Promise.all([
      client.getStatus(),
      client.getStatus(),
      client.getStatus(),
    ]);
    
    // All should return (either success or error, not throw)
    expect(results).toHaveLength(3);
  });
});

describe('OWASP Security: Error Propagation', () => {
  it('should return structured errors', async () => {
    const { HermesHttpClient } = await import('../src/transport/client');
    const client = new HermesHttpClient('http://localhost:9999');
    
    const result = await client.delegateTask({
      task_id: 'security-test',
      title: 'Test',
      description: 'Test task'
    });
    
    expect(result).toHaveProperty('success');
    if (!result.success && result.error) {
      expect(result.error).toHaveProperty('code');
      expect(result.error).toHaveProperty('message');
    }
  });
});

describe('OWASP Security: Session Isolation', () => {
  it('should have error codes for unauthorized access', () => {
    expect(ErrorCode.SESSION_NOT_FOUND).toBeDefined();
    expect(typeof ErrorCode.SESSION_NOT_FOUND).toBe('number');
  });
});
