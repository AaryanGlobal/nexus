/// <reference types="vitest" />

import { defineConfig } from 'vite';

export default defineConfig({
  test: {
    testTimeout: 30000,
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
    include: ['tests/**/*.test.ts'],
  },
});