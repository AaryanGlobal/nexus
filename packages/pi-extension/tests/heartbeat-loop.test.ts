/**
 * TDD: Periodic Heartbeat Loop Tests
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock HermesHttpClient to avoid undici issues
vi.mock('../src/transport/client', () => ({
  HermesHttpClient: class MockHttpClient {
    delegateTask = vi.fn();
    reportResult = vi.fn();
    reportReady = vi.fn();
    heartbeat = vi.fn();
    getStatus = vi.fn();
    constructor(_url: string, _token?: string) {}
  },
  __esModule: true
}));

import { HermesBridge } from '../src/index';

describe('NHIL: Periodic Heartbeat Loop', () => {
  const config = {
    hermesUrl: 'http://localhost:9999',
    authToken: 'test',
  };

  describe('Heartbeat Scheduling', () => {
    it('should have heartbeat interval method', () => {
      const bridge = new HermesBridge(config);
      expect(typeof (bridge as any).startHeartbeat).toBe('function');
      expect(typeof (bridge as any).stopHeartbeat).toBe('function');
    });

    it('heartbeat interval default should be 30 seconds', () => {
      const bridge = new HermesBridge(config);
      const interval = (bridge as any).heartbeatInterval;
      expect(interval).toBe(30000);
    });

    it('should accept custom heartbeat interval', () => {
      const customConfig = { ...config, heartbeatIntervalMs: 60000 };
      const bridge = new HermesBridge(customConfig as any);
      expect((bridge as any).heartbeatInterval).toBe(60000);
    });
  });

  describe('Task Timeout Handler', () => {
    it('should have timeout check method', () => {
      const bridge = new HermesBridge(config);
      expect(typeof (bridge as any).checkTimeouts).toBe('function');
    });
  });
});
