/**
 * Playwright test fixtures with worker-scoped port allocation
 *
 * This prevents port conflicts when running tests in parallel by assigning
 * each worker a unique port based on its workerIndex.
 *
 * Base port: 6113
 * Worker 0: 6113
 * Worker 1: 6114
 * Worker 2: 6115
 * etc.
 */

import { test as base } from '@playwright/test';

const BASE_PORT = 6113;

export const test = base.extend({
  /**
   * Worker-scoped port fixture.
   * All workers share the single webServer port because Playwright starts
   * only one global server. The previous per-worker port allocation was
   * inconsistent with the global webServer config and left non-zero workers
   * pointing at a non-existent port.
   */
  port: [
    async ({}, use, workerInfo) => {
      const port = BASE_PORT;
      console.log(`Worker ${workerInfo.workerIndex} using port ${port}`);
      await use(port);
    },
    { scope: 'worker' },
  ],

  /**
   * Worker-scoped baseURL fixture
   * Automatically set based on the worker's assigned port
   */
  baseURL: async ({ port }, use) => {
    const baseURL = `http://localhost:${port}`;
    await use(baseURL);
  },
});

export { expect } from '@playwright/test';
