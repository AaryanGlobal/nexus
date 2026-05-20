/**
 * pi tools for Hermes bridge.
 */

import { HermesHttpClient } from './transport/client';

/**
 * Hermes delegate tool definition.
 */
export const hermesDelegateTool = {
  name: 'hermes_delegate',
  description: 'Delegate a subtask to Hermes agent',
  parameters: {
    type: 'object' as const,
    properties: {
      task: { 
        type: 'string' as const, 
        description: 'Task description' 
      },
      context: { 
        type: 'string' as const, 
        description: 'Additional context' 
      },
      priority: {
        type: 'string' as const,
        enum: ['low', 'normal', 'high'] as const,
        default: 'normal' as const,
        description: 'Task priority'
      }
    },
    required: ['task'] as const
  },
};

/**
 * Hermes result reporting tool definition.
 */
export const hermesResultTool = {
  name: 'hermes_report_result',
  description: 'Report task result to Hermes',
  parameters: {
    type: 'object' as const,
    properties: {
      kanban_id: { 
        type: 'string' as const, 
        description: 'Kanban ID from Hermes' 
      },
      status: { 
        type: 'string' as const, 
        enum: ['success', 'partial', 'failed', 'blocked'] as const,
        description: 'Task outcome' 
      },
      summary: { 
        type: 'string' as const, 
        description: 'Result summary' 
      },
      artifacts: {
        type: 'array' as const,
        items: { type: 'string' as const },
        description: 'Files created'
      },
      errors: {
        type: 'array' as const, 
        items: { type: 'string' as const },
        description: 'Error messages if failed'
      }
    },
    required: ['kanban_id', 'status', 'summary'] as const
  },
};
