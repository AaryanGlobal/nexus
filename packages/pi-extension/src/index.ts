/**
 * Hermes-Pi Bridge Extension for pi
 * 
 * Enables pi to receive tasks from Hermes and report results.
 * Features:
 * - HTTP delegation (non-blocking)
 * - WebSocket push notifications (results pushed when ready)
 * - Automatic reconnection
 * - NHIL orchestration hooks
 * 
 * Logging is silent by default to avoid polluting pi output.
 */

import { Type } from "typebox";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";

// Re-export types
export * from './types';

// Config
export { BridgeConfig, loadConfig } from './config';

// Heartbeat (crash recovery)
export { TaskHeartbeat, HeartbeatEntry, InterruptedTask } from './heartbeat';

// Transport
export { HermesHttpClient } from './transport/client';
export { HermesWebSocketClient, HermesMessage } from './transport/websocket-client';

// Persistent bridge for push-based results
export { PersistentBridge, NHILOrchestrator } from './bridge/persistent-bridge';

// ============================================================================
// Logging - controlled via environment variable to avoid polluting pi output
// ============================================================================

const LOG_LEVEL = process.env.HERMES_BRIDGE_LOG_LEVEL || 'error'; // default: error only

function _log(..._args: unknown[]) {
  if (LOG_LEVEL === 'debug' || LOG_LEVEL === 'info') {
    console.log('[HermesBridge]', ..._args);
  }
}

function _warn(..._args: unknown[]) {
  if (LOG_LEVEL === 'debug' || LOG_LEVEL === 'info' || LOG_LEVEL === 'warn') {
    console.warn('[HermesBridge]', ..._args);
  }
}

function _error(...args: unknown[]) {
  // Errors always logged but only to stderr, not mixed with stdout
  console.error('[HermesBridge]', ...args);
}

function _debug(..._args: unknown[]) {
  if (LOG_LEVEL === 'debug') {
    console.log('[HermesBridge DEBUG]', ..._args);
  }
}

// ============================================================================
// Bridge Implementation
// ============================================================================

import { HermesHttpClient } from './transport/client';
import { HermesWebSocketClient, HermesMessage } from './transport/websocket-client';

export interface HermesBridgeConfig {
  hermesUrl: string;
  wsUrl?: string;
  sessionId?: string;
  taskId?: string;
  authToken?: string;
  heartbeatIntervalMs?: number;
  onTaskResult?: (result: TaskResult) => void | Promise<void>;
}

export interface TaskResult {
  kanban_id: string;
  status: 'success' | 'partial' | 'failed' | 'blocked';
  summary: string;
  artifacts?: string[];
  errors?: string[];
  timestamp?: number;
}

/**
 * Hermes Bridge with WebSocket push support.
 */
export class HermesBridge {
  private httpClient: HermesHttpClient;
  private wsClient: HermesWebSocketClient | null = null;
  private config: HermesBridgeConfig;
  private heartbeatInterval: number;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private isRunning: boolean = false;
  private pendingDelegations: Map<string, (result: TaskResult) => void> = new Map();
  private resultHandlers: ((result: TaskResult) => void | Promise<void>)[] = [];

  constructor(config: HermesBridgeConfig) {
    this.config = config;
    this.httpClient = new HermesHttpClient(config.hermesUrl, config.authToken);
    this.heartbeatInterval = config.heartbeatIntervalMs ?? 30000;
    
    if (config.wsUrl) {
      this.wsClient = new HermesWebSocketClient({
        url: config.wsUrl,
        authToken: config.authToken,
        onMessage: (msg: HermesMessage) => this.handlePushMessage(msg),
        onConnect: () => {
          _log('WebSocket connected');
          this.subscribeToResults();
        },
        onDisconnect: () => {
          _log('WebSocket disconnected');
        },
      });
    }
  }

  async start(): Promise<void> {
    if (this.isRunning) return;
    this.isRunning = true;

    if (this.wsClient) {
      try {
        await this.wsClient.connect();
      } catch (err) {
        _warn('WebSocket connection failed');
        this.wsClient = null;
      }
    }

    this.startHeartbeat();
    await this.reportReady();
  }

  stop(): void {
    this.isRunning = false;
    this.stopHeartbeat();
    this.wsClient?.disconnect();
  }

  onTaskResult(handler: (result: TaskResult) => void | Promise<void>): void {
    this.resultHandlers.push(handler);
  }

  async delegate(
    title: string,
    description: string,
    onResult?: (result: TaskResult) => void,
    priority?: string
  ): Promise<string> {
    const taskId = crypto.randomUUID();
    
    if (onResult) {
      this.pendingDelegations.set(taskId, onResult);
    }

    const result = await this.httpClient.delegateTask({
      task_id: taskId,
      title: title.substring(0, 50),
      description,
      priority: priority || 'normal',
    });

    if (!result.success) {
      this.pendingDelegations.delete(taskId);
      throw new Error(`Delegation failed: ${result.error?.message}`);
    }

    _log('Delegated', result.data!.kanban_id);
    return result.data!.kanban_id;
  }

  get hasPushConnection(): boolean {
    return this.wsClient?.isConnected() ?? false;
  }

  async checkTimeouts(): Promise<void> {
    try {
      const status = await this.httpClient.getStatus();
      if (!status.success) {
        _warn('Hermes unavailable');
      }
    } catch (err) {
      _error('Timeout check failed');
    }
  }

  getHttpClient(): HermesHttpClient {
    return this.httpClient;
  }

  createDelegateTool() {
    return defineTool({
      name: 'hermes_delegate',
      label: 'Delegate to Hermes',
      description: 'Delegate a subtask to Hermes agent for planning or reasoning',
      promptSnippet: 'Delegate a task to Hermes when needed',
      parameters: Type.Object({
        title: Type.String({ description: 'Task title (max 50 chars)' }),
        description: Type.String({ description: 'Task description' }),
        context: Type.Optional(Type.String({ description: 'Additional context' })),
        priority: Type.Optional(Type.String({ enum: ['low', 'normal', 'high'], default: 'normal' })),
      }),
      execute: async (_id, params) => {
        try {
          const kanbanId = await this.delegate(
            params.title as string,
            params.description as string,
            undefined,
            params.priority as string | undefined
          );
          return {
            content: [{ type: 'text', text: JSON.stringify({ success: true, kanban_id: kanbanId }) }],
            details: {},
          };
        } catch (err) {
          return {
            content: [{ type: 'text', text: JSON.stringify({ 
              success: false, 
              error: { message: err instanceof Error ? err.message : 'Error' } 
            }) }],
            details: {},
            isError: true,
          };
        }
      },
    });
  }

  createResultTool() {
    return defineTool({
      name: 'hermes_report_result',
      label: 'Report Result to Hermes',
      description: 'Report task result back to Hermes',
      promptSnippet: 'Report result when task is complete',
      parameters: Type.Object({
        kanban_id: Type.String({ description: 'Kanban ID' }),
        status: Type.String({ enum: ['success', 'partial', 'failed', 'blocked'] }),
        summary: Type.String({ description: 'Result summary' }),
        artifacts: Type.Optional(Type.Array(Type.String())),
        errors: Type.Optional(Type.Array(Type.String())),
      }),
      execute: async (_id, params) => {
        try {
          const result = await this.httpClient.reportResult({
            task_id: params.kanban_id as string,
            status: params.status as 'success' | 'partial' | 'failed' | 'blocked',
            summary: params.summary as string,
            artifacts: params.artifacts as string[] | undefined,
            errors: params.errors as string[] | undefined,
          });
          return {
            content: [{ type: 'text', text: JSON.stringify(result) }],
            details: {},
          };
        } catch (err) {
          return {
            content: [{ type: 'text', text: JSON.stringify({ 
              success: false, 
              error: { message: err instanceof Error ? err.message : 'Error' } 
            }) }],
            details: {},
            isError: true,
          };
        }
      },
    });
  }

  register(ctx: { registerTool: (tool: unknown) => void }) {
    ctx.registerTool(this.createDelegateTool());
    ctx.registerTool(this.createResultTool());
  }

  private handlePushMessage(message: HermesMessage): void {
    if (message.type === 'task_result' && message.kanban_id) {
      const result: TaskResult = {
        kanban_id: message.kanban_id,
        status: message.status || 'failed',
        summary: message.summary || '',
        artifacts: message.artifacts?.map(a => a.path),
        errors: message.errors,
        timestamp: message.timestamp,
      };

      _log('Push received:', result.kanban_id);
      this.deliverResult(result);
    }
  }

  private deliverResult(result: TaskResult): void {
    for (const handler of this.resultHandlers) {
      try {
        const response = handler(result);
        if (response instanceof Promise) {
          response.catch(e => _error('Handler error'));
        }
      } catch (err) {
        _error('Handler threw');
      }
    }
  }

  private subscribeToResults(): void {
    this.wsClient?.send({ type: 'subscribe', channel: 'task_results' });
  }

  private startHeartbeat(): void {
    if (this.heartbeatTimer) return;
    
    this.sendHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this.sendHeartbeat();
    }, this.heartbeatInterval);
    // Silent - heartbeat is internal only, shouldn't pollute pi output
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private async sendHeartbeat(): Promise<void> {
    try {
      await this.httpClient.heartbeat(this.config.sessionId ?? 'default');
      // Silent - heartbeat is internal only, shouldn't pollute pi output
    } catch (err) {
      _debug('Heartbeat failed');
    }
  }

  async reportReady(): Promise<void> {
    try {
      await this.httpClient.reportReady(
        this.config.sessionId ?? 'default',
        this.config.taskId
      );
    } catch (err) {
      _error('Failed to report ready');
    }
  }
}

// ============================================================================
// Pi Extension Entry Point
// ============================================================================

function loadConfig(): HermesBridgeConfig {
  return {
    hermesUrl: process.env.HERMES_URL || 'http://localhost:8080',
    wsUrl: process.env.HERMES_WS_URL || 'ws://localhost:8080/ws',
    sessionId: process.env.HERMES_SESSION_ID || crypto.randomUUID(),
    authToken: process.env.HERMES_AUTH_TOKEN || '',
    heartbeatIntervalMs: parseInt(process.env.HERMES_HEARTBEAT_INTERVAL || '30000', 10),
    taskId: process.env.HERMES_TASK_ID,
  };
}

const config = loadConfig();
const bridge = new HermesBridge(config);

export default async function piExtension(pi: ExtensionAPI): Promise<void> {
  try {
    await bridge.start();
  } catch (err) {
    _error('Failed to start bridge');
  }

  pi.registerTool(bridge.createDelegateTool());
  pi.registerTool(bridge.createResultTool());

  bridge.onTaskResult((result) => {
    // Emit result via structured log for external consumption
    console.log(`[HERMES_RESULT] ${result.kanban_id}:${result.status}`);
  });

  pi.on('session_shutdown', () => {
    bridge.stop();
  });

  _log('Extension loaded');
}