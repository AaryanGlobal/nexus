// Mock pi-coding-agent to avoid undici import issues in Node.js 22
// This file MUST be loaded before any imports

import { vi } from 'vitest';

// Mock @earendil-works/pi-coding-agent
vi.mock('@earendil-works/pi-coding-agent', () => ({
  HermesBridge: {
    create: () => ({
      registerTool: vi.fn(),
      on: vi.fn(),
      start: vi.fn().mockResolvedValue(undefined),
      stop: vi.fn(),
    }),
  },
  piExtension: vi.fn(),
  defineTool: vi.fn().mockImplementation(() => ({
    name: 'mock-tool',
    description: 'mock',
    execute: vi.fn(),
  })),
  default: {
    HermesBridge: {
      create: () => ({
        registerTool: vi.fn(),
        on: vi.fn(),
      }),
    },
  },
}));

export {};
