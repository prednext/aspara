// @ts-check
import { defineConfig, devices } from '@playwright/test';

const BASE_PORT = 6113;

/**
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  // Target only E2E tests (avoid conflicts with Vitest)
  testDir: './tests/e2e',

  // Number of parallel workers
  // 2 workers in CI, unlimited locally
  workers: process.env.CI ? 2 : undefined,

  // Test execution timeout
  timeout: 30 * 1000,

  // Test expectations
  expect: {
    // Maximum wait time for an element to become visible
    timeout: 5000,
  },

  // Take screenshots of failed tests
  use: {
    // Base URL
    baseURL: `http://localhost:${BASE_PORT}`,

    // Take screenshots
    screenshot: 'only-on-failure',

    // Record traces
    trace: 'on-first-retry',

    // Allow downloads
    acceptDownloads: true,
  },

  // Test report format
  // 'list' only outputs to the console and does not generate an HTML report
  reporter: process.env.CI ? 'github' : 'list',

  // Automatically start the server before tests
  webServer: {
    command: `uv run aspara dashboard --port ${BASE_PORT}`,
    port: BASE_PORT,
    reuseExistingServer: !process.env.CI,
    timeout: 60 * 1000,
  },

  // Project settings
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
});
