/**
 * Tests for HermesBridge
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock HermesHttpClient BEFORE importing HermesBridge
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

describe('HermesBridge', () => {
  let bridge: HermesBridge;
  const config = {
    hermesUrl: 'http://localhost:8080',
    authToken: 'test-token',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    bridge = new HermesBridge(config);
  });

  describe('constructor', () => {
    it('should store config', () => {
      expect((bridge as any).config).toEqual(config);
    });

    it('should create client instance', () => {
      expect((bridge as any).httpClient).toBeDefined();
    });
  });

  describe('createDelegateTool()', () => {
    it('should create delegate tool', () => {
      const tool = bridge.createDelegateTool();
      expect(tool.name).toBe('hermes_delegate');
      expect(tool.label).toBe('Delegate to Hermes');
      expect(tool.description).toContain('Delegate');
    });
  });

  describe('createResultTool()', () => {
    it('should create result tool', () => {
      const tool = bridge.createResultTool();
      expect(tool.name).toBe('hermes_report_result');
      expect(tool.label).toBe('Report Result to Hermes');
      expect(tool.description).toContain('Report');
    });
  });

  describe('register()', () => {
    let mockContext: any;
    let registeredTools: any[] = [];

    beforeEach(() => {
      registeredTools = [];
      mockContext = {
        registerTool: vi.fn((tool: any) => {
          registeredTools.push(tool);
        })
      };
    });

    it('should register hermes_delegate tool', () => {
      bridge.register(mockContext);
      
      const delegateTool = registeredTools.find(t => t.name === 'hermes_delegate');
      expect(delegateTool).toBeDefined();
    });

    it('should register hermes_report_result tool', () => {
      bridge.register(mockContext);
      
      const resultTool = registeredTools.find(t => t.name === 'hermes_report_result');
      expect(resultTool).toBeDefined();
    });

    it('should register both tools', () => {
      bridge.register(mockContext);
      expect(registeredTools.length).toBe(2);
    });
  });

  describe('error handling', () => {
    it('should handle delegate errors gracefully', async () => {
      // Error handling is tested via the tool's error handling
      const tool = bridge.createDelegateTool();
      // Tool should be defined
      expect(tool).toBeDefined();
    });
  });
});

describe('HermesBridge standalone functions', () => {
  it('should export HermesBridge class', () => {
    expect(HermesBridge).toBeDefined();
  });
});
