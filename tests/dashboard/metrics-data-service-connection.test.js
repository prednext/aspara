import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { MetricsDataService } from '../../src/aspara/dashboard/static/js/metrics/metrics-data-service.js';
import { cleanupTestContainer, createTestContainer, mockFetch } from '../vitest-setup.js';

describe('MetricsDataService connection state callbacks', () => {
  let service;
  let stateChanges;

  beforeEach(() => {
    // Setup EventSource mock
    const mockEventSource = vi.fn(
      class {
        constructor(url) {
          this.url = url;
          this.readyState = 1;
          this.addEventListener = vi.fn();
          this.removeEventListener = vi.fn();
          this.close = vi.fn(() => {
            this.readyState = 2;
          });
        }
      }
    );
    global.EventSource = mockEventSource;

    createTestContainer();

    stateChanges = [];

    service = new MetricsDataService('test_project', {
      onConnectionStateChange: (state, detail) => {
        stateChanges.push({ state, detail });
      },
    });

    // Mock fetch for initial data load
    mockFetch({
      project: 'test_project',
      metrics: {
        loss: {
          run_1: {
            steps: [0],
            values: [1.0],
            timestamps: [1735732800000],
          },
        },
      },
    });
  });

  afterEach(() => {
    service.destroy();
    cleanupTestContainer();
    vi.restoreAllMocks();
  });

  test('notifies connected when SSE opens', async () => {
    await service.fetchAndCacheMetrics(['run_1']);

    // Find the open handler and invoke it
    const openCall = service.eventSource.addEventListener.mock.calls.find((c) => c[0] === 'open');
    expect(openCall).toBeDefined();
    openCall[1]();

    const connectedStates = stateChanges.filter((s) => s.state === 'connected');
    expect(connectedStates.length).toBeGreaterThan(0);
  });

  test('notifies reconnecting when reconnect starts', async () => {
    service.maxReconnectAttempts = 5;
    await service.fetchAndCacheMetrics(['run_1']);

    // Trigger error handler to start reconnection
    const errorCall = service.eventSource.addEventListener.mock.calls.find((c) => c[0] === 'error');
    expect(errorCall).toBeDefined();

    // Mock readyState as CONNECTING (0) so error handler calls reconnectSSE
    service.eventSource.readyState = 0;
    errorCall[1]();

    // Wait for async reconnect to start
    await new Promise((resolve) => setTimeout(resolve, 50));

    const reconnectingStates = stateChanges.filter((s) => s.state === 'reconnecting');
    expect(reconnectingStates.length).toBeGreaterThan(0);
    expect(reconnectingStates[0].detail.attempt).toBe(1);
    expect(reconnectingStates[0].detail.max).toBe(5);
  });

  test('notifies disconnected when max retries reached', async () => {
    service.maxReconnectAttempts = 2;
    service.reconnectAttempts = 2;

    // Calling reconnectSSE should hit the max retry check
    await service.reconnectSSE();

    const disconnectedStates = stateChanges.filter((s) => s.state === 'disconnected');
    expect(disconnectedStates.length).toBe(1);
    expect(disconnectedStates[0].detail).toHaveProperty('lastEventTime');
  });

  test('lastEventTime is updated on metric events', async () => {
    await service.fetchAndCacheMetrics(['run_1']);

    const beforeTime = service.lastEventTime;
    expect(beforeTime).toBe(0);

    // Find and invoke the metric handler
    const metricCall = service.eventSource.addEventListener.mock.calls.find((c) => c[0] === 'metric');
    expect(metricCall).toBeDefined();

    const mockEvent = {
      data: JSON.stringify({
        run: 'run_1',
        step: 1,
        metrics: { loss: 0.5 },
        timestamp: new Date().toISOString(),
      }),
    };
    metricCall[1](mockEvent);

    expect(service.lastEventTime).toBeGreaterThan(0);
  });
});
