/**
 * Unit tests for SSEReconnectManager — the single source of truth for
 * SSE reconnection constants, backoff calculation, guard logic, and
 * connection state notification.
 */
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { SSEReconnectManager } from '../../src/aspara/dashboard/static/js/sse-reconnect-manager.js';

describe('SSEReconnectManager', () => {
  describe('Default constants', () => {
    test('static constants have correct values', () => {
      expect(SSEReconnectManager.MAX_RECONNECT_ATTEMPTS).toBe(10);
      expect(SSEReconnectManager.BASE_RECONNECT_DELAY_MS).toBe(1000);
      expect(SSEReconnectManager.MAX_RECONNECT_DELAY_MS).toBe(30000);
    });

    test('constructor uses defaults when no options provided', () => {
      const mgr = new SSEReconnectManager();
      expect(mgr.maxReconnectAttempts).toBe(10);
      expect(mgr.baseReconnectDelay).toBe(1000);
      expect(mgr.maxReconnectDelay).toBe(30000);
      expect(mgr.isReconnecting).toBe(false);
      expect(mgr.reconnectAttempts).toBe(0);
    });

    test('constructor respects custom options', () => {
      const mgr = new SSEReconnectManager({
        maxReconnectAttempts: 5,
        baseReconnectDelay: 500,
        maxReconnectDelay: 10000,
      });
      expect(mgr.maxReconnectAttempts).toBe(5);
      expect(mgr.baseReconnectDelay).toBe(500);
      expect(mgr.maxReconnectDelay).toBe(10000);
    });
  });

  describe('calculateBackoffDelay', () => {
    test('returns base delay for first attempt', () => {
      const mgr = new SSEReconnectManager();
      expect(mgr.calculateBackoffDelay(1)).toBe(1000);
    });

    test('doubles delay for each subsequent attempt', () => {
      const mgr = new SSEReconnectManager();
      expect(mgr.calculateBackoffDelay(1)).toBe(1000);
      expect(mgr.calculateBackoffDelay(2)).toBe(2000);
      expect(mgr.calculateBackoffDelay(3)).toBe(4000);
      expect(mgr.calculateBackoffDelay(4)).toBe(8000);
      expect(mgr.calculateBackoffDelay(5)).toBe(16000);
    });

    test('caps delay at maxReconnectDelay', () => {
      const mgr = new SSEReconnectManager();
      // 2^5 * 1000 = 32000, should cap at 30000
      expect(mgr.calculateBackoffDelay(6)).toBe(30000);
      expect(mgr.calculateBackoffDelay(10)).toBe(30000);
    });

    test('respects custom base and max', () => {
      const mgr = new SSEReconnectManager({
        baseReconnectDelay: 500,
        maxReconnectDelay: 5000,
      });
      expect(mgr.calculateBackoffDelay(1)).toBe(500);
      expect(mgr.calculateBackoffDelay(2)).toBe(1000);
      expect(mgr.calculateBackoffDelay(4)).toBe(4000);
      // 2^4 * 500 = 8000, should cap at 5000
      expect(mgr.calculateBackoffDelay(5)).toBe(5000);
    });
  });

  describe('canReconnect', () => {
    test('returns true when idle and under max attempts', () => {
      const mgr = new SSEReconnectManager();
      expect(mgr.canReconnect()).toBe(true);
    });

    test('returns false when already reconnecting', () => {
      const mgr = new SSEReconnectManager();
      mgr.isReconnecting = true;
      expect(mgr.canReconnect()).toBe(false);
    });

    test('returns false when max attempts reached', () => {
      const mgr = new SSEReconnectManager();
      mgr.reconnectAttempts = 10;
      expect(mgr.canReconnect()).toBe(false);
    });

    test('returns false when both reconnecting and at max', () => {
      const mgr = new SSEReconnectManager();
      mgr.isReconnecting = true;
      mgr.reconnectAttempts = 10;
      expect(mgr.canReconnect()).toBe(false);
    });
  });

  describe('beginReconnect', () => {
    test('sets isReconnecting to true', () => {
      const mgr = new SSEReconnectManager();
      mgr.beginReconnect();
      expect(mgr.isReconnecting).toBe(true);
    });

    test('increments reconnectAttempts', () => {
      const mgr = new SSEReconnectManager();
      expect(mgr.reconnectAttempts).toBe(0);
      mgr.beginReconnect();
      expect(mgr.reconnectAttempts).toBe(1);
      mgr.beginReconnect();
      expect(mgr.reconnectAttempts).toBe(2);
    });

    test('notifies reconnecting state with attempt and max', () => {
      const states = [];
      const mgr = new SSEReconnectManager({
        onConnectionStateChange: (state, detail) => states.push({ state, detail }),
      });
      mgr.beginReconnect();
      expect(states).toHaveLength(1);
      expect(states[0].state).toBe('reconnecting');
      expect(states[0].detail.attempt).toBe(1);
      expect(states[0].detail.max).toBe(10);
    });
  });

  describe('resetReconnectState', () => {
    test('resets isReconnecting and reconnectAttempts', () => {
      const mgr = new SSEReconnectManager();
      mgr.beginReconnect();
      mgr.beginReconnect();
      expect(mgr.isReconnecting).toBe(true);
      expect(mgr.reconnectAttempts).toBe(2);

      mgr.resetReconnectState();
      expect(mgr.isReconnecting).toBe(false);
      expect(mgr.reconnectAttempts).toBe(0);
    });
  });

  describe('notifyConnectionState', () => {
    test('calls onConnectionStateChange callback', () => {
      const states = [];
      const mgr = new SSEReconnectManager({
        onConnectionStateChange: (state, detail) => states.push({ state, detail }),
      });

      mgr.notifyConnectionState('connected');
      mgr.notifyConnectionState('reconnecting', { attempt: 3 });
      mgr.notifyConnectionState('disconnected', { lastEventTime: 12345 });

      expect(states).toEqual([
        { state: 'connected', detail: {} },
        { state: 'reconnecting', detail: { attempt: 3 } },
        { state: 'disconnected', detail: { lastEventTime: 12345 } },
      ]);
    });

    test('does not throw when no callback is set', () => {
      const mgr = new SSEReconnectManager();
      expect(() => mgr.notifyConnectionState('connected')).not.toThrow();
    });
  });

  describe('Integration: full reconnection cycle', () => {
    test('canReconnect -> beginReconnect -> resetReconnectState cycle', () => {
      const states = [];
      const mgr = new SSEReconnectManager({
        maxReconnectAttempts: 3,
        onConnectionStateChange: (state, detail) => states.push({ state, detail }),
      });

      // First attempt
      expect(mgr.canReconnect()).toBe(true);
      mgr.beginReconnect();
      expect(mgr.isReconnecting).toBe(true);
      expect(mgr.reconnectAttempts).toBe(1);

      // Simulate successful connection
      mgr.resetReconnectState();
      mgr.notifyConnectionState('connected');
      expect(mgr.isReconnecting).toBe(false);
      expect(mgr.reconnectAttempts).toBe(0);

      // Second attempt
      expect(mgr.canReconnect()).toBe(true);
      mgr.beginReconnect();
      expect(mgr.reconnectAttempts).toBe(1);

      // Max attempts reached after more failures
      mgr.reconnectAttempts = 3;
      expect(mgr.canReconnect()).toBe(false);
    });
  });
});
