/**
 * NHIL Self-Correction Loop Tests - Integration Style
 */

import { describe, it, expect } from 'vitest';
import HermesBridge, { BridgeConfig } from '../src/index';
import { HermesHttpClient } from '../src/transport/client';

describe('NHIL: Self-Correction Loop', () => {
  const config: BridgeConfig = {
    hermesUrl: 'http://localhost:9999', // Test server
    piPort: 2719,
    authToken: 'test-token',
  };

  describe('Client Methods', () => {
    it('HermesHttpClient has all required methods', () => {
      const client = new HermesHttpClient('http://localhost:9999');
      expect(typeof client.getStatus).toBe('function');
      expect(typeof client.delegateTask).toBe('function');
      expect(typeof client.reportResult).toBe('function');
      expect(typeof client.reportReady).toBe('function');
      expect(typeof client.heartbeat).toBe('function');
    });
  });

  describe('HermesBridge Setup', () => {
    it('should create bridge with config', () => {
      const bridge = new HermesBridge(config);
      expect((bridge as any).config).toEqual(config);
      expect((bridge as any).client).toBeDefined();
    });

    it('should reportReady without throwing', async () => {
      const bridge = new HermesBridge(config);
      await expect(bridge.reportReady()).resolves.not.toThrow();
    });
  });

  describe('Error Handling', () => {
    it('getStatus returns error when server unavailable', async () => {
      const client = new HermesHttpClient('http://localhost:9999');
      const result = await client.getStatus();
      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
    });

    it('delegateTask returns error when server unavailable', async () => {
      const client = new HermesHttpClient('http://localhost:9999');
      const result = await client.delegateTask({
        task_id: 'test-1',
        title: 'Test',
        description: 'Test task'
      });
      expect(result.success).toBe(false);
    });

    it('reportResult returns error when server unavailable', async () => {
      const client = new HermesHttpClient('http://localhost:9999');
      const result = await client.reportResult({
        task_id: 'test-1',
        status: 'success',
        summary: 'Done'
      });
      expect(result.success).toBe(false);
    });
  });

  describe('API Endpoints', () => {
    it('all endpoints are defined in client', async () => {
      const client = new HermesHttpClient('http://localhost:9999');
      
      // These should not throw, just make requests
      await expect(client.heartbeat('session-1')).resolves.not.toThrow();
      await expect(client.reportReady('session-1', 'task-1')).resolves.not.toThrow();
    });
  });
});
