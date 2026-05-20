/**
 * Hermes-Pi Bridge HTTP Server for pi.
 * 
 * This server runs alongside pi and exposes an HTTP API for Hermes
 * to delegate tasks and receive results.
 */

import * as http from 'http';
import * as path from 'path';
import * as os from 'os';
import { URL } from 'url';
import {
  TaskDelegateRequest,
  TaskResultRequest,
  PROTOCOL_VERSION,
  ErrorCode,
} from './types';
import { TaskHeartbeat } from './heartbeat';

/** Generate a unique ID */
function generateId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older environments
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Task in the queue.
 */
interface QueuedTask {
  task_id: string;
  title: string;
  description: string;
  context?: {
    workspace: string;
    files?: string[];
    checkpoint_hash?: string;
  };
  timeout_seconds: number;
  priority: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  result?: {
    status: string;
    summary: string;
    artifacts?: Array<{ path: string; type: string }>;
    errors?: string[];
  };
  created_at: number;
  started_at?: number;
  completed_at?: number;
}

/**
 * Server configuration.
 */
export interface BridgeServerConfig {
  port: number;
  host: string;
  authToken?: string;
  maxConcurrent: number;
}

/**
 * Default configuration.
 */
const DEFAULT_CONFIG: BridgeServerConfig = {
  port: 2719,
  host: '0.0.0.0',
  maxConcurrent: 2,
};

/**
 * Bridge HTTP Server.
 */
export class BridgeServer {
  private config: BridgeServerConfig;
  private server?: http.Server;
  private tasks: Map<string, QueuedTask> = new Map();
  private taskQueue: string[] = [];
  private runningTasks: Set<string> = new Set();
  private heartbeat: TaskHeartbeat;

  constructor(config: Partial<BridgeServerConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    // Initialize heartbeat in pi's agent directory
    const dataDir = path.join(os.homedir(), '.pi', 'agent', '.hermes-bridge');
    this.heartbeat = new TaskHeartbeat(dataDir);
  }

  /**
   * Start the server and recover any interrupted tasks.
   */
  async start(): Promise<void> {
    return new Promise((resolve, reject) => {
      // Recover interrupted tasks from previous session
      const interrupted = this.heartbeat.recoverInterrupted();
      if (interrupted.length > 0) {
        console.log(`Recovered ${interrupted.length} interrupted tasks:`,
          interrupted.map(t => t.task_id).join(', '));
        // TODO: Report these as interrupted to Hermes
      }

      this.server = http.createServer((req, res) => {
        this.handleRequest(req, res).catch(err => {
          console.error('Request handling error:', err);
        });
      });

      this.server.on('error', (err) => {
        reject(err);
      });

      this.server.listen(this.config.port, this.config.host, () => {
        console.log(`Bridge server listening on ${this.config.host}:${this.config.port}`);
        resolve();
      });
    });
  }

  /**
   * Stop the server.
   */
  async stop(): Promise<void> {
    return new Promise((resolve) => {
      if (this.server) {
        this.server.close(() => {
          resolve();
        });
      } else {
        resolve();
      }
    });
  }

  /**
   * Handle incoming HTTP request.
   */
  private async handleRequest(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    // CORS headers
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

    // Handle CORS preflight
    if (req.method === 'OPTIONS') {
      res.writeHead(204);
      res.end();
      return;
    }

    // Only accept POST and GET
    if (req.method !== 'POST' && req.method !== 'GET') {
      this.sendError(res, 405, -32600, 'Method not allowed');
      return;
    }

    // Parse URL
    const url = new URL(req.url || '/', `http://${req.headers.host}`);
    const pathname = url.pathname;

    // Auth check (if token configured)
    if (this.config.authToken) {
      const auth = req.headers.authorization;
      if (!auth || auth !== `Bearer ${this.config.authToken}`) {
        this.sendError(res, 401, ErrorCode.AUTH_ERROR, 'Unauthorized');
        return;
      }
    }

    // Route request
    try {
      if (pathname === '/api/v1/agent.status' && req.method === 'POST') {
        await this.handleAgentStatus(req, res);
      } else if (pathname === '/api/v1/task.delegate' && req.method === 'POST') {
        await this.handleTaskDelegate(req, res);
      } else if (pathname === '/api/v1/task.result' && req.method === 'POST') {
        await this.handleTaskResult(req, res);
      } else if (pathname === '/api/v1/task.status' && req.method === 'POST') {
        await this.handleTaskStatus(req, res);
      } else if (pathname === '/api/v1/task.cancel' && req.method === 'POST') {
        await this.handleTaskCancel(req, res);
      } else if (pathname === '/api/v1/agent.ready' && req.method === 'POST') {
        await this.handleAgentReady(req, res);
      } else if (pathname === '/api/v1/health' && req.method === 'GET') {
        this.handleHealthCheck(req, res);
      } else {
        this.sendError(res, 404, ErrorCode.METHOD_NOT_FOUND, 'Endpoint not found');
      }
    } catch (err) {
      console.error('Handler error:', err);
      this.sendError(res, 500, ErrorCode.INTERNAL_ERROR, 'Internal error');
    }
  }

  /**
   * Handle agent.status request.
   */
  private async handleAgentStatus(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    const body = await this.readBody(req);
    const data = JSON.parse(body);

    // Check version compatibility
    const clientVersion = data.version || '0.0.0';
    const [clientMajor] = clientVersion.split('.').map(Number);
    const [serverMajor] = PROTOCOL_VERSION.split('.').map(Number);

    if (clientMajor !== serverMajor) {
      this.sendError(res, 200, ErrorCode.VERSION_MISMATCH, 'Version mismatch', {
        client_version: clientVersion,
        server_version: PROTOCOL_VERSION,
      });
      return;
    }

    this.sendJson(res, {
      jsonrpc: '2.0',
      result: {
        available: true,
        version: PROTOCOL_VERSION,
        capabilities: ['delegate', 'status', 'result'],
        max_concurrent: this.config.maxConcurrent,
        current_load: this.runningTasks.size,
      },
      id: data.id || null,
    });
  }

  /**
   * Handle task.delegate request.
   */
  private async handleTaskDelegate(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    const body = await this.readBody(req);
    const data = JSON.parse(body);

    // Validate request
    if (!data.title && !data.description) {
      this.sendError(res, 200, ErrorCode.INVALID_PARAMS, 'Missing title and description');
      return;
    }

    // Create task
    const taskId = data.task_id || generateId();
    const task: QueuedTask = {
      task_id: taskId,
      title: (data.title || data.description || '').substring(0, 50),
      description: data.description || data.title || '',
      context: data.context,
      timeout_seconds: data.timeout_seconds || 300,
      priority: data.priority || 'normal',
      status: 'pending',
      created_at: Date.now(),
    };

    this.tasks.set(taskId, task);
    this.taskQueue.push(taskId);

    // Process queue
    this.processQueue();

    this.sendJson(res, {
      jsonrpc: '2.0',
      result: {
        task_id: taskId,
        status: 'accepted',
      },
      id: data.id || null,
    });
  }

  /**
   * Handle task.result request (from pi tools).
   */
  private async handleTaskResult(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    const body = await this.readBody(req);
    const data = JSON.parse(body);

    const taskId = data.task_id;
    if (!taskId) {
      this.sendError(res, 200, ErrorCode.INVALID_PARAMS, 'Missing task_id');
      return;
    }

    const task = this.tasks.get(taskId);
    if (!task) {
      this.sendError(res, 200, ErrorCode.TASK_NOT_FOUND, `Task ${taskId} not found`);
      return;
    }

    // Update task with result
    task.status = data.status === 'success' ? 'completed' : 'failed';
    task.result = {
      status: data.status,
      summary: data.summary || '',
      artifacts: data.artifacts,
      errors: data.errors,
    };
    task.completed_at = Date.now();

    // Update heartbeat for crash recovery
    this.heartbeat.beat(taskId, task.status);

    // Remove from running
    this.runningTasks.delete(taskId);

    // Process next in queue
    this.processQueue();

    this.sendJson(res, {
      jsonrpc: '2.0',
      result: {
        acknowledged: true,
        task_id: taskId,
      },
      id: data.id || null,
    });
  }

  /**
   * Handle task.status request.
   */
  private async handleTaskStatus(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    const body = await this.readBody(req);
    const data = JSON.parse(body);

    const taskId = data.task_id;
    if (!taskId) {
      this.sendError(res, 200, ErrorCode.INVALID_PARAMS, 'Missing task_id');
      return;
    }

    const task = this.tasks.get(taskId);
    if (!task) {
      this.sendError(res, 200, ErrorCode.TASK_NOT_FOUND, `Task ${taskId} not found`);
      return;
    }

    this.sendJson(res, {
      jsonrpc: '2.0',
      result: {
        task_id: taskId,
        status: task.status,
        progress_percent: this.calculateProgress(task),
        started_at: task.started_at,
        completed_at: task.completed_at,
      },
      id: data.id || null,
    });
  }

  /**
   * Handle task.cancel request.
   */
  private async handleTaskCancel(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    const body = await this.readBody(req);
    const data = JSON.parse(body);

    const taskId = data.task_id;
    if (!taskId) {
      this.sendError(res, 200, ErrorCode.INVALID_PARAMS, 'Missing task_id');
      return;
    }

    const task = this.tasks.get(taskId);
    if (!task) {
      this.sendError(res, 200, ErrorCode.TASK_NOT_FOUND, `Task ${taskId} not found`);
      return;
    }

    task.status = 'cancelled';
    task.completed_at = Date.now();

    // Update heartbeat for crash recovery
    this.heartbeat.beat(taskId, 'cancelled');
    this.runningTasks.delete(taskId);

    // Remove from queue
    const queueIndex = this.taskQueue.indexOf(taskId);
    if (queueIndex > -1) {
      this.taskQueue.splice(queueIndex, 1);
    }

    this.sendJson(res, {
      jsonrpc: '2.0',
      result: {
        cancelled: true,
        task_id: taskId,
      },
      id: data.id || null,
    });
  }

  /**
   * Handle agent.ready notification.
   */
  private async handleAgentReady(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    this.sendJson(res, {
      jsonrpc: '2.0',
      result: {
        acknowledged: true,
      },
      id: null,
    });
  }

  /**
   * Handle health check.
   */
  private handleHealthCheck(req: http.IncomingMessage, res: http.ServerResponse): void {
    this.sendJson(res, {
      status: 'ok',
      version: PROTOCOL_VERSION,
      tasks: {
        total: this.tasks.size,
        running: this.runningTasks.size,
        queued: this.taskQueue.length,
      },
    });
  }

  /**
   * Process the task queue.
   */
  private processQueue(): void {
    // Start tasks up to max concurrent
    while (
      this.runningTasks.size < this.config.maxConcurrent &&
      this.taskQueue.length > 0
    ) {
      const taskId = this.taskQueue.shift();
      if (taskId) {
        const task = this.tasks.get(taskId);
        if (task && task.status === 'pending') {
          task.status = 'running';
          task.started_at = Date.now();
          this.runningTasks.add(taskId);

          // Record heartbeat for crash recovery
          this.heartbeat.beat(taskId, 'running');

          // Emit event for pi to pick up
          this.onTaskReady(task);
        }
      }
    }
  }

  /**
   * Called when a task is ready to be processed.
   * Override or set callback to handle task.
   */
  private onTaskReady(task: QueuedTask): void {
    // This should be overridden or emit an event
    // For now, just log
    console.log(`Task ready: ${task.task_id} - ${task.title}`);
  }

  /**
   * Calculate task progress percentage.
   */
  private calculateProgress(task: QueuedTask): number {
    switch (task.status) {
      case 'pending':
        return 0;
      case 'running':
        if (!task.started_at) return 0;
        const elapsed = Date.now() - task.started_at;
        const timeout = task.timeout_seconds * 1000;
        return Math.min(90, Math.round((elapsed / timeout) * 100));
      case 'completed':
        return 100;
      case 'failed':
      case 'cancelled':
        return 100;
      default:
        return 0;
    }
  }

  /**
   * Read request body.
   */
  private readBody(req: http.IncomingMessage): Promise<string> {
    return new Promise((resolve, reject) => {
      let body = '';
      req.on('data', chunk => {
        body += chunk.toString();
      });
      req.on('end', () => resolve(body));
      req.on('error', reject);
    });
  }

  /**
   * Send JSON response.
   */
  private sendJson(res: http.ServerResponse, data: object): void {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
  }

  /**
   * Send error response.
   */
  private sendError(
    res: http.ServerResponse,
    statusCode: number,
    code: number,
    message: string,
    data?: object
  ): void {
    res.writeHead(statusCode, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      jsonrpc: '2.0',
      error: {
        code,
        message,
        ...(data && { data }),
      },
      id: null,
    }));
  }
}

/**
 * Start the server if running as main module.
 */
if (require.main === module) {
  const config: BridgeServerConfig = {
    port: parseInt(process.env.PORT || '2719', 10),
    host: process.env.HOST || '0.0.0.0',
    authToken: process.env.AUTH_TOKEN,
    maxConcurrent: parseInt(process.env.MAX_CONCURRENT || '2', 10),
  };

  const server = new BridgeServer(config);
  
  server.start().then(() => {
    console.log('Bridge server started');
  }).catch(err => {
    console.error('Failed to start server:', err);
    process.exit(1);
  });

  // Handle shutdown
  process.on('SIGINT', async () => {
    console.log('Shutting down...');
    await server.stop();
    process.exit(0);
  });
}
