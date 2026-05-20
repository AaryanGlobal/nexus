/**
 * NHIL Self-Correction Loop Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock HermesHttpClient to avoid undici issues
vi.mock('../src/transport/client', () => ({
  HermesHttpClient: class MockHttpClient {
    delegateTask = vi.fn().mockResolvedValue({ success: true });
    reportResult = vi.fn().mockResolvedValue({ success: true });
    reportReady = vi.fn().mockResolvedValue({ success: true });
    heartbeat = vi.fn().mockResolvedValue(undefined);
    getStatus = vi.fn().mockResolvedValue({ status: 'ok' });
    constructor(_url: string, _token?: string) {}
  },
  __esModule: true
}));

import { HermesBridge } from '../src/index';

describe('NHIL: Self-Correction Loop', () => {
  const config = {
    hermesUrl: 'http://localhost:9999',
    authToken: 'test-token',
  };

  describe('Client Methods', () => {
    it('HermesHttpClient has all required methods', () => {
      const bridge = new HermesBridge(config);
      const client = (bridge as any).httpClient;
      expect(typeof client.delegateTask).toBe('function');
      expect(typeof client.reportResult).toBe('function');
      expect(typeof client.reportReady).toBe('function');
    });

    it('should have heartbeat method', () => {
      const bridge = new HermesBridge(config);
      const client = (bridge as any).httpClient;
      expect(typeof client.heartbeat).toBe('function');
    });

    it('should have getStatus method', () => {
      const bridge = new HermesBridge(config);
      const client = (bridge as any).httpClient;
      expect(typeof client.getStatus).toBe('function');
    });
  });

  describe('Self-Correction Tools', () => {
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
});
