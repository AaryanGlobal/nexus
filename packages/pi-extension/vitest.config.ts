/// <reference types="vitest" />

import { defineConfig } from 'vite';

export default defineConfig({
  test: {
    testTimeout: 30000,
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'html'],
      exclude: [
        'node_modules/**',
        'dist/**',
        '**/*.test.ts',
        '**/*.spec.ts',
        'tests/**',
      ],
    },
    // Include tests that work without undici issues
    include: [
      'tests/types.test.ts',
      'tests/security.test.ts',
      'tests/transport.test.ts',
      'tests/heartbeat-recovery.test.ts',
      'tests/server.test.ts',
      'tests/index.test.ts',
    ],
    // Exclude tests that import HermesBridge directly
    exclude: [
      'tests/heartbeat-loop.test.ts',
      'tests/self-correction.test.ts',
    ],
  },
});