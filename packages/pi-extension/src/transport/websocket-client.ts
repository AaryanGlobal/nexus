/**
 * WebSocket transport client for Hermes push notifications.
 */

import { URL } from 'url';

// Silent logging
function _log(..._args: unknown[]) { /* silent */ }
function _error(...args: unknown[]) {
  console.error('[HermesWS]', ...args);
}

export type MessageHandler = (message: HermesMessage) => void;
export type ConnectionHandler = () => void;
export type ErrorHandler = (error: Error) => void;

export interface HermesMessage {
  type: 'task_result' | 'task_update' | 'ping' | 'error';
  task_id?: string;
  kanban_id?: string;
  status?: 'success' | 'partial' | 'failed' | 'blocked';
  summary?: string;
  artifacts?: Array<{ path: string; type: string }>;
  errors?: string[];
  error?: { code: number; message: string };
  timestamp?: number;
}

export interface WebSocketOptions {
  url: string;
  authToken?: string;
  reconnectDelayMs?: number;
  maxReconnectAttempts?: number;
  onMessage?: MessageHandler;
  onConnect?: ConnectionHandler;
  onDisconnect?: ConnectionHandler;
  onError?: ErrorHandler;
}

export class HermesWebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private authToken: string;
  private reconnectDelayMs: number;
  private maxReconnectAttempts: number;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private shouldReconnect = true;
  private isConnecting = false;
  
  onMessage?: MessageHandler;
  onConnect?: ConnectionHandler;
  onDisconnect?: ConnectionHandler;
  onError?: ErrorHandler;

  constructor(options: WebSocketOptions) {
    this.url = options.url;
    this.authToken = options.authToken || '';
    this.reconnectDelayMs = options.reconnectDelayMs || 1000;
    this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
    this.onMessage = options.onMessage;
    this.onConnect = options.onConnect;
    this.onDisconnect = options.onDisconnect;
    this.onError = options.onError;
  }

  async connect(): Promise<void> {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    this.isConnecting = true;
    this.shouldReconnect = true;

    return new Promise((resolve, reject) => {
      try {
        let wsUrl = this.url;
        if (this.authToken) {
          const url = new URL(this.url);
          url.searchParams.set('token', this.authToken);
          wsUrl = url.toString();
        }

        this.ws = new WebSocket(wsUrl);
        this.ws.binaryType = 'arraybuffer';

        this.ws.onopen = () => {
          _log('Connected');
          this.isConnecting = false;
          this.reconnectAttempts = 0;
          this.startPingInterval();
          this.onConnect?.();
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: HermesMessage = JSON.parse(event.data);
            
            if (message.type === 'ping') {
              this.send({ type: 'pong', timestamp: Date.now() });
              return;
            }

            this.onMessage?.(message);
          } catch (e) {
            _error('Parse failed');
          }
        };

        this.ws.onerror = () => {
          _error('Error');
          this.onError?.(new Error('WebSocket error'));
        };

        this.ws.onclose = (event) => {
          _log('Disconnected', event.code);
          this.isConnecting = false;
          this.stopPingInterval();
          this.onDisconnect?.();
          
          if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect();
          }
        };

      } catch (err) {
        this.isConnecting = false;
        reject(err);
      }
    });
  }

  disconnect(): void {
    this.shouldReconnect = false;
    this.stopPingInterval();
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
  }

  send(message: Record<string, unknown>): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  subscribeToTask(kanbanId: string): void {
    this.send({ type: 'subscribe', kanban_id: kanbanId });
  }

  unsubscribeFromTask(kanbanId: string): void {
    this.send({ type: 'unsubscribe', kanban_id: kanbanId });
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  private startPingInterval(): void {
    this.pingInterval = setInterval(() => {
      if (this.isConnected()) {
        this.send({ type: 'ping', timestamp: Date.now() });
      }
    }, 30000);
  }

  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private scheduleReconnect(): void {
    this.reconnectAttempts++;
    const delay = Math.min(
      this.reconnectDelayMs * Math.pow(2, this.reconnectAttempts - 1),
      60000
    );
    
    _log('Reconnecting in', delay, 'ms');
    
    this.reconnectTimer = setTimeout(() => {
      this.connect().catch(() => {
        _error('Reconnect failed');
      });
    }, delay);
  }
}