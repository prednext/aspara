/**
 * Unit tests for RunsListSSE reconnection backoff
 */

import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

// Mock sse-utils before import
vi.mock('../../src/aspara/dashboard/static/js/runs-list/sse-utils.js', () => ({
  INITIAL_SINCE_TIMESTAMP: 0,
  buildSSEUrl: vi.fn(() => '/api/sse'),
  extractRunNamesFromElements: vi.fn(() => ['run-1', 'run-2']),
  isConnectionClosed: vi.fn(() => true),
  parseStatusUpdate: vi.fn(() => null),
  updateRunStatusIcon: vi.fn(),
}));

import { RunsListSSE } from '../../src/aspara/dashboard/static/js/runs-list/sse.js';

// Fake EventSource that stays in CONNECTING state (no auto-error).
class FakeEventSource {
  constructor(url) {
    this.url = url;
    this.readyState = 0; // CONNECTING
    this.listeners = {};
  }

  addEventListener(name, handler) {
    if (!this.listeners[name]) {
      this.listeners[name] = [];
    }
    this.listeners[name].push(handler);
  }

  removeEventListener(name, handler) {
    if (this.listeners[name]) {
      this.listeners[name] = this.listeners[name].filter((h) => h !== handler);
    }
  }

  close() {
    this.readyState = 2; // CLOSED
  }

  _dispatch(name, event) {
    for (const h of this.listeners[name] || []) {
      h(event);
    }
  }
}

describe('RunsListSSE reconnection backoff', () => {
  let originalEventSource;
  let setupSseSpy;

  beforeEach(() => {
    vi.useFakeTimers();
    originalEventSource = global.EventSource;
    global.EventSource = FakeEventSource;
    document.body.innerHTML = '<div data-run="run-1"></div><div data-run="run-2"></div>';
  });

  afterEach(() => {
    vi.useRealTimers();
    global.EventSource = originalEventSource;
    document.body.innerHTML = '';
  });

  function createSSE() {
    const sse = new RunsListSSE('test-project');
    setupSseSpy = vi.spyOn(sse, 'setupSSE');
    // Prevent setupSSE from creating real EventSource on reconnect.
    setupSseSpy.mockImplementation(() => {
      sse.eventSource = new FakeEventSource('/api/sse');
    });
    return sse;
  }

  test('first reconnect should use 1s delay (baseReconnectDelay)', () => {
    const sse = createSSE();

    sse.reconnect();
    expect(sse.reconnectManager.reconnectAttempts).toBe(1);
    expect(sse.reconnectManager.isReconnecting).toBe(true);

    // setupSSE should NOT have been called yet (delay not elapsed).
    expect(setupSseSpy).not.toHaveBeenCalled();

    // Advance just under 1s — nothing should happen.
    vi.advanceTimersByTime(999);
    expect(setupSseSpy).not.toHaveBeenCalled();

    // Advance the remaining 1ms to trigger the setTimeout callback.
    vi.advanceTimersByTime(1);
    expect(setupSseSpy).toHaveBeenCalledTimes(1);

    sse.destroy();
  });

  test('second reconnect should use 2s delay (exponential backoff)', () => {
    const sse = createSSE();

    // First reconnect (1s delay).
    sse.reconnect();
    expect(sse.reconnectManager.reconnectAttempts).toBe(1);
    vi.advanceTimersByTime(1000);
    expect(setupSseSpy).toHaveBeenCalledTimes(1);

    // Reset isReconnecting to simulate the 'open' handler not firing
    // (FakeEventSource doesn't auto-dispatch 'open'). This allows the
    // second reconnect() call to proceed.
    sse.reconnectManager.isReconnecting = false;

    // Second reconnect (2s delay).
    sse.reconnect();
    expect(sse.reconnectManager.reconnectAttempts).toBe(2);

    // Advance just under 2s — setupSSE should NOT have been called again.
    vi.advanceTimersByTime(1999);
    expect(setupSseSpy).toHaveBeenCalledTimes(1);

    // Advance the remaining 1ms.
    vi.advanceTimersByTime(1);
    expect(setupSseSpy).toHaveBeenCalledTimes(2);

    sse.destroy();
  });

  test('should give up after maxReconnectAttempts', () => {
    const sse = createSSE();
    sse.reconnectManager.maxReconnectAttempts = 3;

    // Attempt 1 (1s)
    sse.reconnect();
    expect(sse.reconnectManager.reconnectAttempts).toBe(1);
    vi.advanceTimersByTime(1000);
    sse.reconnectManager.isReconnecting = false;

    // Attempt 2 (2s)
    sse.reconnect();
    expect(sse.reconnectManager.reconnectAttempts).toBe(2);
    vi.advanceTimersByTime(2000);
    sse.reconnectManager.isReconnecting = false;

    // Attempt 3 (4s)
    sse.reconnect();
    expect(sse.reconnectManager.reconnectAttempts).toBe(3);
    vi.advanceTimersByTime(4000);
    sse.reconnectManager.isReconnecting = false;

    // Should have given up — no attempt 4.
    sse.reconnect();
    expect(sse.reconnectManager.reconnectAttempts).toBe(3);
    expect(setupSseSpy).toHaveBeenCalledTimes(3);

    sse.destroy();
  });

  test('should not start concurrent reconnections', () => {
    const sse = createSSE();

    sse.reconnect();
    expect(sse.reconnectManager.reconnectAttempts).toBe(1);
    expect(sse.reconnectManager.isReconnecting).toBe(true);

    // Manually call reconnect() again — should be skipped.
    sse.reconnect();
    expect(sse.reconnectManager.reconnectAttempts).toBe(1);

    sse.destroy();
  });

  test('destroy should reset reconnection state', () => {
    const sse = createSSE();

    sse.reconnect();
    expect(sse.reconnectManager.isReconnecting).toBe(true);
    expect(sse.reconnectManager.reconnectAttempts).toBe(1);

    sse.destroy();
    expect(sse.reconnectManager.isReconnecting).toBe(false);
    expect(sse.reconnectManager.reconnectAttempts).toBe(0);
  });
});
