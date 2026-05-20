/**
 * Hermes-Pi Bridge for pi
 * 
 * Enables pi to receive tasks from Hermes and report results.
 * Installed via: pi install npm:hermes-pi-bridge
 * 
 * This extension registers tools for communicating with Hermes.
 */

// Re-export types
export * from './types';

// Config
export { BridgeConfig, loadConfig } from './config';

// Heartbeat (crash recovery)
export { TaskHeartbeat, HeartbeatEntry, InterruptedTask } from './heartbeat';

// Transport
export { HermesHttpClient } from './transport/client';

// Tools
export { hermesDelegateTool, hermesResultTool } from './tools';

// Import client at module level for proper mocking
import { HermesHttpClient } from './transport/client';

/**
 * pi extension context interface.
 * Provided by pi runtime when loading the extension.
 */
interface PiExtensionContext {
  registerTool(tool: PiTool): void;
}

interface PiTool {
  name: string;
  description: string;
  parameters: object;
  execute: (
    toolCallId: string, 
    params: Record<string, unknown>,
    signal: AbortSignal,
    onUpdate: (update: unknown) => void
  ) => Promise<string>;
}

/**
 * Hermes bridge configuration.
 */
export interface HermesBridgeConfig {
  hermesUrl: string;
  sessionId: string;
  taskId?: string;
  authToken?: string;
}

/**
 * Hermes bridge extension.
 */
export class HermesBridge {
  private client: HermesHttpClient;
  private config: HermesBridgeConfig;
  private heartbeatInterval: number;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private isRunning: boolean = false;
  
  constructor(config: HermesBridgeConfig) {
    this.config = config;
    this.client = new HermesHttpClient(config.hermesUrl, config.authToken);
    this.heartbeatInterval = 30000; // 30 seconds default
    
    // Override heartbeat interval if provided
    if ('heartbeatIntervalMs' in config && typeof config.heartbeatIntervalMs === 'number') {
      this.heartbeatInterval = config.heartbeatIntervalMs;
    }
  }
  
  /**
   * Start the periodic heartbeat loop.
   * This keeps the NHIL autonomous loop alive.
   */
  startHeartbeat(): void {
    if (this.isRunning) return;
    this.isRunning = true;
    
    // Send initial heartbeat
    this.sendHeartbeat();
    
    // Schedule periodic heartbeat
    this.heartbeatTimer = setInterval(() => {
      this.sendHeartbeat();
    }, this.heartbeatInterval);
    
    console.log(`[HermesBridge] Heartbeat loop started (${this.heartbeatInterval}ms)`);
  }
  
  /**
   * Stop the periodic heartbeat loop.
   */
  stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    this.isRunning = false;
    console.log('[HermesBridge] Heartbeat loop stopped');
  }
  
  /**
   * Send a single heartbeat to Hermes.
   */
  private async sendHeartbeat(): Promise<void> {
    try {
      await this.client.heartbeat(this.config.sessionId);
      console.debug('[HermesBridge] Heartbeat sent');
    } catch (error) {
      console.error('[HermesBridge] Heartbeat failed:', error);
    }
  }
  
  /**
   * Check for expired tasks and report timeout.
   * Should be called periodically.
   */
  async checkTimeouts(): Promise<void> {
    // This would typically check local task state
    // For now, just ensure connection is alive
    try {
      const status = await this.client.getStatus();
      if (!status.success) {
        console.warn('[HermesBridge] Hermes unavailable, tasks may be stuck');
      }
    } catch (error) {
      console.error('[HermesBridge] Timeout check failed:', error);
    }
  }
  
  /**
   * Register all bridge tools with pi.
   */
  register(ctx: PiExtensionContext): void {
    // Register delegate tool
    ctx.registerTool({
      name: 'hermes_delegate',
      description: 'Delegate a subtask to Hermes agent',
      parameters: {
        type: 'object',
        properties: {
          task: { 
            type: 'string', 
            description: 'Task description' 
          },
          context: { 
            type: 'string', 
            description: 'Additional context' 
          },
          priority: {
            type: 'string',
            enum: ['low', 'normal', 'high'],
            default: 'normal',
            description: 'Task priority'
          }
        },
        required: ['task']
      },
      execute: async (toolCallId, params, signal, onUpdate) => {
        // Actually call the Hermes HTTP client - NOT a stub!
        try {
          const result = await this.client.delegateTask({
            task_id: crypto.randomUUID(),
            title: (params.task as string).substring(0, 50),
            description: params.task as string,
            priority: (params.priority as string) || 'normal',
          });
          
          if (result.success && result.data) {
            return JSON.stringify({
              success: true,
              kanban_id: result.data.kanban_id,
              status: result.data.status
            });
          } else {
            return JSON.stringify({
              success: false,
              error: result.error || { code: -32603, message: 'Unknown error' }
            });
          }
        } catch (error) {
          return JSON.stringify({
            success: false,
            error: { 
              code: -32603, 
              message: error instanceof Error ? error.message : 'Internal error' 
            }
          });
        }
      }
    });
    
    // Register result reporting tool
    ctx.registerTool({
      name: 'hermes_report_result',
      description: 'Report task result to Hermes',
      parameters: {
        type: 'object',
        properties: {
          kanban_id: { 
            type: 'string', 
            description: 'Kanban ID from Hermes' 
          },
          status: { 
            type: 'string', 
            enum: ['success', 'partial', 'failed', 'blocked'],
            description: 'Task outcome' 
          },
          summary: { 
            type: 'string', 
            description: 'Result summary' 
          },
          artifacts: {
            type: 'array',
            items: { type: 'string' },
            description: 'Files created'
          },
          errors: {
            type: 'array', 
            items: { type: 'string' },
            description: 'Error messages if failed'
          }
        },
        required: ['kanban_id', 'status', 'summary']
      },
      execute: async (toolCallId, params, signal, onUpdate) => {
        try {
          const result = await this.client.reportResult({
            task_id: params.kanban_id as string,
            status: params.status as 'success' | 'partial' | 'failed' | 'blocked',
            summary: params.summary as string,
            artifacts: params.artifacts as string[] | undefined,
            errors: params.errors as string[] | undefined,
          });
          
          return JSON.stringify(result);
        } catch (error) {
          return JSON.stringify({
            success: false,
            error: { 
              code: -32603, 
              message: error instanceof Error ? error.message : 'Internal error' 
            }
          });
        }
      }
    });
  }
  
  /**
   * Report ready to Hermes.
   */
  async reportReady(): Promise<void> {
    try {
      await this.client.reportReady(this.config.sessionId, this.config.taskId);
    } catch (error) {
      // Log but don't throw - ready report is non-critical
      console.error('Failed to report ready to Hermes:', error);
    }
  }
  
  /**
   * Get the HTTP client for external use.
   */
  getClient(): HermesHttpClient {
    return this.client;
  }
}

// Default export for pi extension loader
export default HermesBridge;