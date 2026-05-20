/**
 * Shared type definitions for Hermes-Pi Bridge.
 * 
 * These types mirror the Python types in the core package
 * to ensure protocol compatibility.
 */

/** Type of agent - use as const object */
export const AgentType = {
  HERMES: 'hermes',
  PI: 'pi',
} as const;
export type AgentType = typeof AgentType[keyof typeof AgentType];

/** Status of a delegated task */
export const TaskStatus = {
  PENDING: 'pending',
  RUNNING: 'running',
  SUCCESS: 'success',
  PARTIAL: 'partial',
  FAILED: 'failed',
  BLOCKED: 'blocked',
  CANCELLED: 'cancelled',
} as const;
export type TaskStatus = typeof TaskStatus[keyof typeof TaskStatus];

/** Task priority */
export const Priority = {
  LOW: 'low',
  NORMAL: 'normal',
  HIGH: 'high',
} as const;
export type Priority = typeof Priority[keyof typeof Priority];

/** Protocol version */
export interface ProtocolVersion {
  major: number;
  minor: number;
  patch: number;
}

/** Agent status response */
export interface AgentStatusResponse {
  agent_type: AgentType;
  version: string;
  available: boolean;
  capabilities: string[];
  max_concurrent: number;
  uptime_seconds?: number;
}

/** Task context for delegation */
export interface TaskContext {
  workspace: string;
  files?: string[];
  checkpoint_hash?: string;
  environment?: Record<string, string>;
}

/** Request to delegate a task */
export type TaskDelegateRequest = {
  task_id?: string;
  title: string;
  description: string;
  context?: TaskContext;
  timeout_seconds?: number;
  priority?: Priority;
};

/** Result of a completed task */
export type TaskResultRequest = {
  task_id: string;
  status: 'success' | 'partial' | 'failed' | 'blocked';
  summary: string;
  artifacts?: TaskArtifact[];
  errors?: string[];
  checkpoint_hash?: string;
  duration_seconds?: number;
};

/** Artifact created by a task */
export interface TaskArtifact {
  path: string;
  type: 'file' | 'directory' | 'other';
  checksum?: string;
}

/** Standard API error response */
export interface ApiError {
  code: number;
  message: string;
  data?: Record<string, unknown>;
}

/** Standard API response wrapper */
export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: ApiError;
}

/** JSON-RPC 2.0 request */
export interface JsonRpcRequest {
  jsonrpc: '2.0';
  method: string;
  params?: Record<string, unknown>;
  id: string;
}

/** JSON-RPC 2.0 success response */
export interface JsonRpcSuccessResponse {
  jsonrpc: '2.0';
  result: unknown;
  id: string;
}

/** JSON-RPC 2.0 error response */
export interface JsonRpcErrorResponse {
  jsonrpc: '2.0';
  error: ApiError;
  id: string;
}

/** JSON-RPC 2.0 response (success or error) */
export type JsonRpcResponse = JsonRpcSuccessResponse | JsonRpcErrorResponse;

/** Version compatibility info */
export const PROTOCOL_VERSION = '1.0.0';

/** Error codes */
export const ErrorCode = {
  PARSE_ERROR: -32700,
  INVALID_REQUEST: -32600,
  METHOD_NOT_FOUND: -32601,
  INVALID_PARAMS: -32602,
  INTERNAL_ERROR: -32603,
  AUTH_ERROR: 1000,
  SESSION_NOT_FOUND: 1001,
  TASK_NOT_FOUND: 1002,
  TIMEOUT: 1003,
  CAPACITY_EXCEEDED: 1004,
  VERSION_MISMATCH: 1005,
  CONTEXT_CONFLICT: 1006,
} as const;
