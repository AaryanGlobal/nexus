/**
 * NHIL Self-Correction Loop Tests - Integration Style
 */

import { describe, it, expect, vi } from 'vitest';
import { HermesBridge } from '../src/index';
import { HermesHttpClient } from '../src/transport/client';

describe('NHIL: Self-Correction Loop', () => {
  const config = {
    hermesUrl: 'http://localhost:9999',
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
      expect((bridge as any).httpClient).toBeDefined();
    });

    it('should reportReady without throwing', async () => {
      const bridge = new HermesBridge(config);
      await expect(bridge.reportReady()).resolves.not.toThrow();
    });

    it('should create delegate tool', () => {
      const bridge = new HermesBridge(config);
      const tool = bridge.createDelegateTool();
      expect(tool.name).toBe('hermes_delegate');
    });

    it('should create result tool', () => {
      const bridge = new HermesBridge(config);
      const tool = bridge.createResultTool();
      expect(tool.name).toBe('hermes_report_result');
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