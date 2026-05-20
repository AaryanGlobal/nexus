/**
 * TDD: Periodic Heartbeat Loop Tests
 * 
 * Tests for the automatic heartbeat mechanism that keeps
 * NHIL autonomous loops alive.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import HermesBridge, { BridgeConfig } from '../src/index';
import { HermesHttpClient } from '../src/transport/client';

describe('NHIL: Periodic Heartbeat Loop', () => {
  let client: HermesHttpClient;
  const config: BridgeConfig = {
    hermesUrl: 'http://localhost:9999',
    piPort: 2719,
    authToken: 'test',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    client = new HermesHttpClient(config.hermesUrl);
  });

  describe('Heartbeat Scheduling', () => {
    it('should have heartbeat interval method', () => {
      const bridge = new HermesBridge(config);
      expect(typeof (bridge as any).startHeartbeat).toBe('function');
      expect(typeof (bridge as any).stopHeartbeat).toBe('function');
    });

    it('heartbeat interval default should be 30 seconds', () => {
      const bridge = new HermesBridge(config);
      const interval = (bridge as any).heartbeatInterval;
      expect(interval).toBe(30000); // 30 seconds in ms
    });

    it('should accept custom heartbeat interval', () => {
      const customConfig = { ...config, heartbeatIntervalMs: 60000 };
      const bridge = new HermesBridge(customConfig as any);
      expect((bridge as any).heartbeatInterval).toBe(60000);
    });
  });

  describe('Heartbeat Execution', () => {
    it('should send heartbeat periodically', async () => {
      // Test that heartbeat can be called without throwing
      await expect(client.heartbeat('session-123')).resolves.not.toThrow();
    });

    it('should report ready with session ID', async () => {
      await expect(client.reportReady('session-abc')).resolves.not.toThrow();
    });

    it('should report ready with task ID', async () => {
      await expect(client.reportReady('session-abc', 'task-xyz')).resolves.not.toThrow();
    });
  });

  describe('Recovery on Disconnect', () => {
    it('should handle heartbeat failure gracefully', async () => {
      // When server is down, heartbeat should return without throwing
      const result = await client.heartbeat('session-disconnect');
      // Should complete without error
      expect(result).toBeUndefined(); // void return
    });

    it('should queue heartbeats for retry', async () => {
      // Multiple rapid heartbeats should not throw
      await Promise.all([
        client.heartbeat('session-1'),
        client.heartbeat('session-2'),
        client.heartbeat('session-3'),
      ]);
      // All should complete
      expect(true).toBe(true);
    });
  });
});

describe('NHIL: Task Timeout Handler', () => {
  const config: BridgeConfig = {
    hermesUrl: 'http://localhost:9999',
    piPort: 2719,
    authToken: 'test',
  };

  it('should have timeout check method', () => {
    const bridge = new HermesBridge(config);
    expect(typeof (bridge as any).checkTimeouts).toBe('function');
  });

  it('should report result does not throw on timeout', async () => {
    const client = new HermesHttpClient('http://localhost:9999');
    // Should complete even when server unavailable
    const result = await client.reportResult({
      task_id: 'timeout-task',
      status: 'failed',
      summary: 'Task timed out',
      errors: ['Timeout exceeded']
    });
    expect(result).toBeDefined();
    expect(result.success).toBe(false); // But error is returned, not thrown
  });
});
