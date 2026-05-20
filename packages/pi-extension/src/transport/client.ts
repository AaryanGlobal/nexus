/**
 * HTTP transport client for Hermes communication.
 */

import * as http from 'http';
import * as https from 'https';
import { URL } from 'url';

import {
  ApiResponse,
  ErrorCode,
  TaskDelegateRequest,
  TaskResultRequest,
  JsonRpcRequest,
} from '../types';

/**
 * HTTP client for communicating with Hermes bridge server.
 */
export class HermesHttpClient {
  private baseUrl: string;
  private authToken: string;
  private timeout: number;

  constructor(
    baseUrl: string = 'http://localhost:8080',
    authToken: string = '',
    timeout: number = 30000
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.authToken = authToken;
    this.timeout = timeout;
  }

  /**
   * Make HTTP request to Hermes server.
   */
  private async request<T>(
    method: string,
    endpoint: string,
    body?: Record<string, unknown>
  ): Promise<ApiResponse<T>> {
    const url = new URL(endpoint, this.baseUrl);
    
    const options: http.RequestOptions = {
      hostname: url.hostname,
      port: url.port || (url.protocol === 'https:' ? 443 : 80),
      path: url.pathname,
      method,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...(this.authToken && { 'Authorization': `Bearer ${this.authToken}` }),
      },
      timeout: this.timeout,
    };

    return new Promise((resolve) => {
      const transport = url.protocol === 'https:' ? https : http;
      
      const req = transport.request(options, (res) => {
        let data = '';
        
        res.on('data', (chunk) => {
          data += chunk;
        });
        
        res.on('end', () => {
          try {
            const parsed = JSON.parse(data);
            resolve({
              success: res.statusCode === 200,
              data: parsed,
            });
          } catch (e) {
            resolve({
              success: false,
              error: {
                code: ErrorCode.PARSE_ERROR,
                message: 'Invalid JSON response',
              },
            });
          }
        });
      });
      
      req.on('error', (e) => {
        resolve({
          success: false,
          error: {
            code: ErrorCode.INTERNAL_ERROR,
            message: e.message,
          },
        });
      });
      
      req.on('timeout', () => {
        req.destroy();
        resolve({
          success: false,
          error: {
            code: ErrorCode.TIMEOUT,
            message: 'Request timed out',
          },
        });
      });
      
      if (body) {
        req.write(JSON.stringify(body));
      }
      
      req.end();
    });
  }

  /**
   * Check Hermes agent status.
   */
  async getStatus(): Promise<ApiResponse<{
    available: boolean;
    version: string;
    capabilities: string[];
    max_concurrent: number;
  }>> {
    return this.request('POST', '/api/v1/agent.status', {
      agent_type: 'hermes',
      version: '1.0.0',
    });
  }

  /**
   * Delegate a task to Hermes.
   */
  async delegateTask(params: {
    task_id: string;
    title: string;
    description: string;
    timeout_seconds?: number;
    priority?: string;
    context?: Record<string, any>;
  }): Promise<ApiResponse<{
    kanban_id: string;
    status: string;
  }>> {
    const title = params.title.length > 50 ? params.title.substring(0, 50) : params.title;
    return this.request('POST', '/api/v1/task.delegate', {
      task_id: params.task_id,
      title,
      description: params.description,
      context: params.context,
      timeout_seconds: params.timeout_seconds || 300,
      priority: params.priority || 'normal',
    });
  }

  /**
   * Report task result to Hermes.
   */
  async reportResult(params: {
    task_id: string;
    status: 'success' | 'partial' | 'failed' | 'blocked';
    summary: string;
    artifacts?: string[];
    errors?: string[];
  }): Promise<ApiResponse<{ acknowledged: boolean }>> {
    return this.request('POST', '/api/v1/task.result', {
      task_id: params.task_id,
      status: params.status,
      summary: params.summary,
      artifacts: params.artifacts?.map(p => ({ path: p, type: 'file' })),
      errors: params.errors,
    });
  }

  /**
   * Report that pi is ready to receive tasks.
   */
  async reportReady(sessionId: string, taskId?: string): Promise<void> {
    await this.request('POST', '/api/v1/agent.ready', {
      agent_type: 'pi',
      version: '1.0.0',
      session_id: sessionId,
      task_id: taskId,
    });
  }

  /**
   * Send heartbeat to Hermes.
   */
  async heartbeat(sessionId: string): Promise<void> {
    await this.request('POST', '/api/v1/agent.heartbeat', {
      session_id: sessionId,
    });
  }
}
