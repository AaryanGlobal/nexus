/**
 * Persistent bridge for async/push-based communication.
 * Logging is silent by default.
 */

import { HermesHttpClient } from '../transport/client';
import { HermesWebSocketClient, HermesMessage } from '../transport/websocket-client';

// Silent logging
function _log(..._args: unknown[]) { /* silent */ }
function _warn(..._args: unknown[]) { /* silent */ }
function _error(...args: unknown[]) {
  console.error('[PersistentBridge]', ...args);
}

interface TaskResult {
  kanban_id: string;
  status: 'success' | 'partial' | 'failed' | 'blocked';
  summary: string;
  artifacts?: string[];
  errors?: string[];
}

type ResultHandler = (result: TaskResult) => void | Promise<void>;

export class PersistentBridge {
  private httpClient: HermesHttpClient;
  private wsClient: HermesWebSocketClient;
  private pendingTasks = new Map<string, ResultHandler>();
  private resultHandlers: ResultHandler[] = [];
  private isConnected = false;

  constructor(config: { hermesUrl: string; wsUrl: string; authToken?: string }) {
    this.httpClient = new HermesHttpClient(config.hermesUrl, config.authToken);
    this.wsClient = new HermesWebSocketClient({
      url: config.wsUrl,
      authToken: config.authToken,
      onMessage: (msg: HermesMessage) => this.handleMessage(msg),
      onConnect: () => {
        _log('Connected');
        this.isConnected = true;
      },
      onDisconnect: () => {
        _log('Disconnected');
        this.isConnected = false;
      },
    });
  }

  async connect(): Promise<void> {
    await this.wsClient.connect();
    this.isConnected = true;
  }

  disconnect(): void {
    this.wsClient.disconnect();
    this.isConnected = false;
  }

  onResult(handler: ResultHandler): void {
    this.resultHandlers.push(handler);
  }

  async delegate(
    title: string,
    description: string,
    onResult?: ResultHandler
  ): Promise<string> {
    const taskId = crypto.randomUUID();
    
    if (onResult) {
      this.pendingTasks.set(taskId, onResult);
    }

    const result = await this.httpClient.delegateTask({
      task_id: taskId,
      title,
      description,
    });

    if (!result.success) {
      this.pendingTasks.delete(taskId);
      throw new Error(`Delegation failed: ${result.error?.message}`);
    }

    return result.data!.kanban_id;
  }

  private handleMessage(message: HermesMessage): void {
    switch (message.type) {
      case 'task_result':
        this.handleTaskResult(message);
        break;
      case 'error':
        _error('Hermes error');
        break;
    }
  }

  private handleTaskResult(message: HermesMessage): void {
    if (!message.kanban_id || !message.status) {
      _warn('Invalid message');
      return;
    }

    const result: TaskResult = {
      kanban_id: message.kanban_id,
      status: message.status,
      summary: message.summary || '',
      artifacts: message.artifacts?.map(a => a.path),
      errors: message.errors,
    };

    for (const handler of this.resultHandlers) {
      try {
        const response = handler(result);
        if (response instanceof Promise) {
          response.catch(() => _error('Handler error'));
        }
      } catch (err) {
        _error('Handler threw');
      }
    }
  }

  get connected(): boolean {
    return this.isConnected;
  }
}

export class NHILOrchestrator {
  private bridge: PersistentBridge;
  private results: TaskResult[] = [];

  constructor(bridge: PersistentBridge) {
    this.bridge = bridge;
    bridge.onResult((result) => {
      this.results.push(result);
    });
  }

  async delegateAndWait(title: string, description: string): Promise<TaskResult> {
    return new Promise((resolve, reject) => {
      this.bridge.delegate(title, description, resolve).catch(reject);
    });
  }

  async delegateFireAndForget(title: string, description: string): Promise<string> {
    return this.bridge.delegate(title, description);
  }

  getResults(): TaskResult[] {
    return [...this.results];
  }
}