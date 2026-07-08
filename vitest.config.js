import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Test environment
    environment: 'jsdom',

    // Test file patterns
    include: ['**/tests/**/*.test.js'],

    // Exclude Playwright tests
    exclude: ['**/node_modules/**', '**/*.spec.js', '**/e2e/**'],

    // Setup files
    setupFiles: ['./tests/vitest-canvas-setup.js', './tests/vitest-setup.js'],

    // Global setup (no need to import describe, it, expect, etc.)
    globals: true,

    // Coverage settings
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'html'],
      include: ['src/aspara/dashboard/static/js/**/*.js'],
      exclude: ['src/aspara/dashboard/static/js/**/*.test.js', 'src/aspara/dashboard/static/js/**/*.spec.js'],
      thresholds: {
        branches: 50,
        functions: 50,
        lines: 50,
        statements: 50,
      },
    },

    // Test timeout
    testTimeout: 10000,

    // DOM environment settings
    environmentOptions: {
      jsdom: {
        url: 'http://localhost',
      },
    },
  },
});
