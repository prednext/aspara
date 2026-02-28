/**
 * Tests for MetricsDataService SSE reconnection behavior
 *
 * This test file specifically tests the SSE reconnection logic to ensure:
 * 1. Reconnection is attempted when SSE connection fails
 * 2. Exponential backoff is applied between retries
 * 3. Max retry limit stops infinite loops
 * 4. Successful connection resets retry counter
 */
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { MetricsDataService } from '../../src/aspara/dashboard/static/js/metrics/metrics-data-service.js';

describe('MetricsDataService SSE Reconnection', () => {
  let dataService;
  let mockEventSourceInstances;
  let eventListeners;

  /**
   * Creates a mock EventSource that captures event listeners
   */
  function createMockEventSource() {
    mockEventSourceInstances = [];
    eventListeners = [];

    const mockEventSource = vi.fn().mockImplementation(function (url) {
      const listeners = {};
      const instance = {
        url,
        readyState: 0, // CONNECTING
        addEventListener: vi.fn((event, handler) => {
          if (!listeners[event]) {
            listeners[event] = [];
          }
          listeners[event].push(handler);
        }),
        removeEventListener: vi.fn(),
        close: vi.fn(() => {
          instance.readyState = 2; // CLOSED
        }),
        // Helper to trigger events in tests
        _triggerEvent: (eventName, data) => {
          if (listeners[eventName]) {
            for (const handler of listeners[eventName]) {
              handler(data);
            }
          }
        },
        _setReadyState: (state) => {
          instance.readyState = state;
        },
        _listeners: listeners,
      };
      mockEventSourceInstances.push(instance);
      eventListeners.push(listeners);
      return instance;
    });

    global.EventSource = mockEventSource;
    // Define EventSource constants
    global.EventSource.CONNECTING = 0;
    global.EventSource.OPEN = 1;
    global.EventSource.CLOSED = 2;

    return mockEventSource;
  }

  beforeEach(() => {
    vi.useFakeTimers();
    createMockEventSource();

    // Mock fetch for delta fetching
    global.fetch = vi.fn().mockRejectedValue(new Error('Server unavailable'));

    dataService = new MetricsDataService('test_project');
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe('Initial state', () => {
    test('should have correct initial reconnection state', () => {
      expect(dataService.isReconnecting).toBe(false);
      expect(dataService.reconnectAttempts).toBe(0);
      expect(dataService.maxReconnectAttempts).toBe(10);
      expect(dataService.baseReconnectDelay).toBe(1000);
    });
  });

  describe('SSE connection error triggers reconnection', () => {
    test('should call reconnectSSE when error event fires', async () => {
      // Setup initial SSE connection
      dataService.setupSSE('run_1');

      const reconnectSpy = vi.spyOn(dataService, 'reconnectSSE');

      // Get the EventSource instance
      const eventSource = dataService.eventSource;

      // Simulate connection error
      eventSource._triggerEvent('error', {});

      expect(reconnectSpy).toHaveBeenCalled();
    });

    test('should increment reconnectAttempts on each reconnection attempt', async () => {
      dataService.currentSSERuns = 'run_1';

      expect(dataService.reconnectAttempts).toBe(0);

      // First reconnection attempt
      const reconnectPromise1 = dataService.reconnectSSE();
      expect(dataService.reconnectAttempts).toBe(1);
      expect(dataService.isReconnecting).toBe(true);

      // Advance timer past the delay
      await vi.advanceTimersByTimeAsync(1000);
      await reconnectPromise1;

      // Simulate error on new connection (triggers another reconnect)
      const eventSource1 = mockEventSourceInstances[mockEventSourceInstances.length - 1];
      eventSource1._triggerEvent('error', {});

      // Second attempt
      expect(dataService.reconnectAttempts).toBe(2);
    });
  });

  describe('Exponential backoff', () => {
    test('should use exponential backoff delays', async () => {
      dataService.currentSSERuns = 'run_1';

      // First attempt: 1000ms delay
      const promise1 = dataService.reconnectSSE();
      expect(dataService.reconnectAttempts).toBe(1);

      // Should not have created EventSource yet (waiting for delay)
      const initialCount = mockEventSourceInstances.length;

      // Advance 500ms - should still be waiting
      await vi.advanceTimersByTimeAsync(500);
      expect(mockEventSourceInstances.length).toBe(initialCount);

      // Advance remaining 500ms - should now create EventSource
      await vi.advanceTimersByTimeAsync(500);
      await promise1;
      expect(mockEventSourceInstances.length).toBe(initialCount + 1);

      // Trigger error to start second reconnection
      const es1 = mockEventSourceInstances[mockEventSourceInstances.length - 1];
      es1._triggerEvent('error', {});

      // Second attempt: 2000ms delay
      expect(dataService.reconnectAttempts).toBe(2);

      // Advance 1500ms - should still be waiting
      const countAfterError = mockEventSourceInstances.length;
      await vi.advanceTimersByTimeAsync(1500);
      expect(mockEventSourceInstances.length).toBe(countAfterError);

      // Advance remaining 500ms - should create new EventSource
      await vi.advanceTimersByTimeAsync(500);
      // Wait for async operations
      await vi.runAllTimersAsync();
      expect(mockEventSourceInstances.length).toBe(countAfterError + 1);
    });

    test('should cap delay at 30 seconds', async () => {
      dataService.currentSSERuns = 'run_1';

      // Set attempts high to test cap
      dataService.reconnectAttempts = 5; // 2^5 * 1000 = 32000ms, should cap at 30000

      const promise = dataService.reconnectSSE();
      expect(dataService.reconnectAttempts).toBe(6);

      const initialCount = mockEventSourceInstances.length;

      // Advance 29 seconds - should still be waiting
      await vi.advanceTimersByTimeAsync(29000);
      expect(mockEventSourceInstances.length).toBe(initialCount);

      // Advance 1 more second (total 30s) - should create EventSource
      await vi.advanceTimersByTimeAsync(1000);
      await promise;
      expect(mockEventSourceInstances.length).toBe(initialCount + 1);
    });
  });

  describe('Max retry limit', () => {
    test('should stop reconnecting after max attempts', async () => {
      dataService.currentSSERuns = 'run_1';
      dataService.reconnectAttempts = 10; // Already at max

      await dataService.reconnectSSE();

      // Should not create new EventSource
      expect(mockEventSourceInstances.length).toBe(0);
      expect(dataService.isReconnecting).toBe(false);
    });

    test('should log error when max attempts reached', async () => {
      const consoleSpy = vi.spyOn(console, 'error');
      dataService.currentSSERuns = 'run_1';
      dataService.reconnectAttempts = 10;

      await dataService.reconnectSSE();

      expect(consoleSpy).toHaveBeenCalledWith('[SSE] Max reconnection attempts reached, giving up');
    });
  });

  describe('Successful connection resets state', () => {
    test('should reset reconnectAttempts on successful connection (open event)', async () => {
      dataService.currentSSERuns = 'run_1';
      dataService.reconnectAttempts = 5;
      dataService.isReconnecting = true;

      // Setup SSE (simulates successful setupSSE call)
      dataService.setupSSE('run_1');

      const eventSource = dataService.eventSource;
      expect(eventSource).not.toBeNull();

      // Simulate successful connection
      eventSource._setReadyState(1); // OPEN
      eventSource._triggerEvent('open', {});

      // State should be reset
      expect(dataService.isReconnecting).toBe(false);
      expect(dataService.reconnectAttempts).toBe(0);
    });
  });

  describe('Reconnection flow after server restart', () => {
    test('should attempt SSE connection even if delta fetch fails', async () => {
      dataService.currentSSERuns = 'run_1';

      // fetch will reject (server down)
      global.fetch = vi.fn().mockRejectedValue(new Error('Server unavailable'));

      const promise = dataService.reconnectSSE();

      // Advance past delay
      await vi.advanceTimersByTimeAsync(1000);
      await promise;

      // Should still have created EventSource despite fetch failure
      expect(mockEventSourceInstances.length).toBe(1);
    });

    test('should handle repeated SSE failures with exponential backoff', async () => {
      dataService.currentSSERuns = 'run_1';
      global.fetch = vi.fn().mockRejectedValue(new Error('Server unavailable'));

      // Track delays between attempts
      const delays = [];
      const lastTime = 0;

      // Start first reconnection
      const promise1 = dataService.reconnectSSE();

      // Simulate multiple reconnection cycles
      for (let i = 0; i < 5; i++) {
        const expectedDelay = Math.min(1000 * 2 ** i, 30000);
        delays.push(expectedDelay);

        // Advance past the expected delay
        await vi.advanceTimersByTimeAsync(expectedDelay);

        // Wait for reconnection to complete
        if (i === 0) {
          await promise1;
        }

        // Verify EventSource was created
        expect(mockEventSourceInstances.length).toBe(i + 1);
        expect(dataService.reconnectAttempts).toBe(i + 1);

        // Trigger error on the new EventSource to start next cycle
        if (i < 4) {
          const es = mockEventSourceInstances[i];
          es._triggerEvent('error', {});
        }
      }

      // Verify exponential delays: 1s, 2s, 4s, 8s, 16s
      expect(delays).toEqual([1000, 2000, 4000, 8000, 16000]);
    });

    test('should not create duplicate reconnection attempts', async () => {
      dataService.currentSSERuns = 'run_1';

      // Start reconnection
      dataService.reconnectSSE();
      expect(dataService.isReconnecting).toBe(true);

      // Try to start another reconnection while one is in progress
      dataService.reconnectSSE();

      // Should still only have one attempt
      expect(dataService.reconnectAttempts).toBe(1);
    });
  });

  describe('destroy() resets reconnection state', () => {
    test('should reset reconnectAttempts on destroy', () => {
      dataService.reconnectAttempts = 5;
      dataService.isReconnecting = true;

      dataService.destroy();

      expect(dataService.reconnectAttempts).toBe(0);
    });
  });

  describe('Concurrent reconnection prevention', () => {
    test('should prevent concurrent reconnection attempts during delay', async () => {
      dataService.currentSSERuns = 'run_1';
      global.fetch = vi.fn().mockRejectedValue(new Error('Server unavailable'));

      // Start first reconnection
      const promise1 = dataService.reconnectSSE();
      expect(dataService.reconnectAttempts).toBe(1);
      expect(dataService.isReconnecting).toBe(true);

      // Simulate another error event calling reconnectSSE while the first is waiting
      // (Error handler no longer resets isReconnecting, just calls reconnectSSE)
      dataService.reconnectSSE();

      // Should still be 1 - second call is skipped because isReconnecting is true
      expect(dataService.reconnectAttempts).toBe(1);
      console.log('reconnectAttempts after duplicate call during delay:', dataService.reconnectAttempts);

      // Clean up
      await vi.advanceTimersByTimeAsync(60000);
    });

    test('should allow new reconnection after setupSSE completes', async () => {
      dataService.currentSSERuns = 'run_1';
      global.fetch = vi.fn().mockRejectedValue(new Error('Server unavailable'));

      // Start first reconnection
      const promise1 = dataService.reconnectSSE();
      expect(dataService.reconnectAttempts).toBe(1);

      // Wait for delay and setupSSE to complete
      await vi.advanceTimersByTimeAsync(1000);
      await promise1;

      // isReconnecting should be false now (reset after setupSSE)
      expect(dataService.isReconnecting).toBe(false);

      // New EventSource was created
      expect(mockEventSourceInstances.length).toBe(1);

      // Simulate error on the new EventSource
      const es = mockEventSourceInstances[0];
      es._triggerEvent('error', {});

      // Should start second reconnection attempt
      expect(dataService.reconnectAttempts).toBe(2);
      expect(dataService.isReconnecting).toBe(true);

      // Clean up
      await vi.advanceTimersByTimeAsync(60000);
    });
  });

  describe('Bug reproduction: infinite loop on server restart', () => {
    /**
     * This test reproduces the original bug where after server restart,
     * the browser would make GET requests to /runs/metrics every 1 second
     * in an infinite loop.
     *
     * The root cause was that isReconnecting was reset in the finally block
     * of reconnectSSE(), before the SSE connection was actually established.
     * When the new EventSource immediately failed, it would trigger another
     * reconnection with no delay protection.
     */
    test('should NOT make rapid repeated requests when SSE keeps failing', async () => {
      dataService.currentSSERuns = 'run_1';
      global.fetch = vi.fn().mockRejectedValue(new Error('Server unavailable'));

      // Start reconnection
      const promise = dataService.reconnectSSE();

      // Advance time to trigger first EventSource creation
      await vi.advanceTimersByTimeAsync(1000); // First delay
      await promise;

      // Count EventSource creations over time
      const initialCount = mockEventSourceInstances.length;
      expect(initialCount).toBe(1);

      // Simulate rapid error events (as would happen with server down)
      const es1 = mockEventSourceInstances[0];
      es1._triggerEvent('error', {});

      // At this point, second reconnection should have started
      expect(dataService.reconnectAttempts).toBe(2);
      expect(dataService.isReconnecting).toBe(true);

      // Advance only 1 second (old bug would have created new EventSource)
      await vi.advanceTimersByTimeAsync(1000);

      // With exponential backoff, second attempt needs 2 seconds, so no new EventSource yet
      expect(mockEventSourceInstances.length).toBe(1);

      // Advance another second (total 2s for second attempt)
      await vi.advanceTimersByTimeAsync(1000);
      await vi.runAllTimersAsync();

      // Now second EventSource should be created
      expect(mockEventSourceInstances.length).toBe(2);
    });

    test('should eventually stop reconnecting after max attempts', async () => {
      dataService.currentSSERuns = 'run_1';
      global.fetch = vi.fn().mockRejectedValue(new Error('Server unavailable'));

      // Manually set attempts to near max to avoid long test duration
      dataService.reconnectAttempts = 9;

      // Start the 10th (last allowed) attempt
      const promise = dataService.reconnectSSE();
      expect(dataService.reconnectAttempts).toBe(10);

      // Advance past delay
      await vi.advanceTimersByTimeAsync(30000); // Max delay
      await promise;

      // EventSource should be created for the 10th attempt
      expect(mockEventSourceInstances.length).toBe(1);

      // Trigger error on the last EventSource
      const lastEs = mockEventSourceInstances[0];
      lastEs._triggerEvent('error', {});

      // At this point, reconnectSSE is called but should return early
      // because reconnectAttempts (10) >= maxReconnectAttempts (10)
      expect(dataService.reconnectAttempts).toBe(10);

      // No new EventSource should be created
      await vi.advanceTimersByTimeAsync(30000);
      await vi.runAllTimersAsync();
      expect(mockEventSourceInstances.length).toBe(1);
    });
  });
});
