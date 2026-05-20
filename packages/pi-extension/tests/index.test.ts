/**
 * Tests for HermesBridge
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { HermesBridge } from '../src/index';

// Use vi.hoisted to define mocks that can be referenced in vi.mock
const { mockDelegateTask, mockReportResult, mockReportReady, mockHeartbeat, mockGetStatus, mockHermesHttpClient } = vi.hoisted(() => ({
  mockDelegateTask: vi.fn(),
  mockReportResult: vi.fn(),
  mockReportReady: vi.fn(),
  mockHeartbeat: vi.fn(),
  mockGetStatus: vi.fn(),
  mockHermesHttpClient: vi.fn().mockImplementation(() => ({
    delegateTask: mockDelegateTask,
    reportResult: mockReportResult,
    reportReady: mockReportReady,
    heartbeat: mockHeartbeat,
    getStatus: mockGetStatus
  }))
}));

// Mock the HermesHttpClient
vi.mock('../src/transport/client', () => ({
  HermesHttpClient: mockHermesHttpClient,
  __esModule: true
}));

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
    it('should create HermesHttpClient with config URL', () => {
      expect(mockHermesHttpClient).toHaveBeenCalledWith(
        config.hermesUrl,
        config.authToken
      );
    });

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
      expect(delegateTool.description).toContain('Delegate');
    });

    it('should register hermes_report_result tool', () => {
      bridge.register(mockContext);
      
      const resultTool = registeredTools.find(t => t.name === 'hermes_report_result');
      expect(resultTool).toBeDefined();
      expect(resultTool.description).toContain('Report');
    });

    it('should register both tools', () => {
      bridge.register(mockContext);
      expect(registeredTools.length).toBe(2);
    });

    describe('hermes_delegate tool execution', () => {
      let delegateTool: any;

      beforeEach(() => {
        bridge.register(mockContext);
        delegateTool = registeredTools.find(t => t.name === 'hermes_delegate');
        mockDelegateTask.mockReset();
        mockDelegateTask.mockResolvedValue({
          success: true,
          data: { kanban_id: 'test-kanban-123', status: 'accepted' }
        });
      });

      it('should call delegateTask with formatted params', async () => {
        const result = await delegateTool.execute(
          'call-1',
          { title: 'Analyze this code', description: 'Analyze this code' }
        );

        expect(mockDelegateTask).toHaveBeenCalledTimes(1);
        const call = mockDelegateTask.mock.calls[0][0];
        expect(call.description).toBe('Analyze this code');
        expect(call.title).toBe('Analyze this code');
        expect(call.priority).toBe('normal');
        expect(call.task_id).toMatch(/^[0-9a-f-]{36}$/);
      });

      it('should truncate title to 50 chars', async () => {
        const longTask = 'A'.repeat(100);
        await delegateTool.execute(
          'call-2',
          { title: longTask, description: longTask }
        );

        const call = mockDelegateTask.mock.calls[0][0];
        expect(call.title.length).toBe(50);
        expect(call.description).toBe(longTask);
      });

      it('should pass priority if provided', async () => {
        await delegateTool.execute(
          'call-3',
          { title: 'Urgent task', description: 'Urgent task', priority: 'high' }
        );

        const call = mockDelegateTask.mock.calls[0][0];
        expect(call.priority).toBe('high');
      });

      it('should return kanban_id on success', async () => {
        mockDelegateTask.mockResolvedValue({
          success: true,
          data: { kanban_id: 'hermes-kanban-abc', status: 'accepted' }
        });

        const result = await delegateTool.execute(
          'call-4',
          { title: 'Test task', description: 'Test task' }
        );

        const parsed = JSON.parse(result.content[0].text);
        expect(parsed.success).toBe(true);
        expect(parsed.kanban_id).toBe('hermes-kanban-abc');
      });

      it('should handle failure', async () => {
        mockDelegateTask.mockResolvedValue({
          success: false,
          error: { code: -32603, message: 'Hermes unavailable' }
        });

        const result = await delegateTool.execute(
          'call-5',
          { title: 'Test task', description: 'Test task' }
        );

        const parsed = JSON.parse(result.content[0].text);
        expect(parsed.success).toBe(false);
        expect(parsed.error.message).toBe('Delegation failed: Hermes unavailable');
      });

      it('should handle exception', async () => {
        mockDelegateTask.mockRejectedValue(new Error('Network error'));

        const result = await delegateTool.execute(
          'call-6',
          { title: 'Test task', description: 'Test task' }
        );

        const parsed = JSON.parse(result.content[0].text);
        expect(parsed.success).toBe(false);
        expect(parsed.error.message).toBe('Network error');
      });
    });

    describe('hermes_report_result tool execution', () => {
      let resultTool: any;

      beforeEach(() => {
        bridge.register(mockContext);
        resultTool = registeredTools.find(t => t.name === 'hermes_report_result');
        mockReportResult.mockReset();
        mockReportResult.mockResolvedValue({
          success: true,
          data: { acknowledged: true }
        });
      });

      it('should call client.reportResult with all fields', async () => {
        await resultTool.execute(
          'call-1',
          {
            kanban_id: 'hermes-task-123',
            status: 'success',
            summary: 'Task completed',
            artifacts: ['/path/to/output.txt'],
            errors: []
          }
        );

        expect(mockReportResult).toHaveBeenCalledWith({
          task_id: 'hermes-task-123',
          status: 'success',
          summary: 'Task completed',
          artifacts: ['/path/to/output.txt'],
          errors: []
        });
      });

      it('should handle failure', async () => {
        mockReportResult.mockResolvedValue({
          success: false,
          error: { code: -32603, message: 'Failed to report' }
        });

        const result = await resultTool.execute(
          'call-2',
          {
            kanban_id: 'task-456',
            status: 'failed',
            summary: 'Task failed'
          }
        );

        const parsed = JSON.parse(result.content[0].text);
        expect(parsed.success).toBe(false);
      });

      it('should handle exception', async () => {
        mockReportResult.mockRejectedValue(new Error('Connection refused'));

        const result = await resultTool.execute(
          'call-3',
          {
            kanban_id: 'task-789',
            status: 'partial',
            summary: 'Partial result'
          }
        );

        const parsed = JSON.parse(result.content[0].text);
        expect(parsed.success).toBe(false);
        expect(parsed.error.message).toBe('Connection refused');
      });

      it('should have required parameters', () => {
        expect(resultTool.parameters.required).toContain('kanban_id');
        expect(resultTool.parameters.required).toContain('status');
        expect(resultTool.parameters.required).toContain('summary');
      });
    });
  });

  describe('reportReady()', () => {
    beforeEach(() => {
      mockReportReady.mockReset();
      mockReportReady.mockResolvedValue({ success: true });
    });

    it('should report ready when bridge connects', async () => {
      await bridge.reportReady();
      expect(mockReportReady).toHaveBeenCalled();
    });

    it('should handle ready report errors gracefully', async () => {
      mockReportReady.mockRejectedValue(new Error('Connection refused'));
      // Should not throw - reportReady catches errors
      await expect(bridge.reportReady()).resolves.not.toThrow();
    });
  });
});