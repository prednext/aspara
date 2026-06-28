import { afterEach, beforeEach, describe, expect, test } from 'vitest';
import { SSEStatusIndicator, buildStatusHTML, formatRelativeTime } from '../../src/aspara/dashboard/static/js/components/sse-status-indicator.js';

describe('formatRelativeTime', () => {
  test('returns empty string for zero or undefined', () => {
    expect(formatRelativeTime(0)).toBe('');
    expect(formatRelativeTime(undefined)).toBe('');
  });

  test('returns "just now" for recent timestamps', () => {
    const now = Date.now();
    expect(formatRelativeTime(now)).toBe('just now');
  });

  test('returns seconds ago', () => {
    const ts = Date.now() - 10000;
    expect(formatRelativeTime(ts)).toBe('10s ago');
  });

  test('returns minutes ago', () => {
    const ts = Date.now() - 120000;
    expect(formatRelativeTime(ts)).toBe('2m ago');
  });

  test('returns hours ago', () => {
    const ts = Date.now() - 7200000;
    expect(formatRelativeTime(ts)).toBe('2h ago');
  });
});

describe('buildStatusHTML', () => {
  test('connected state contains Live label', () => {
    const html = buildStatusHTML('connected');
    expect(html).toContain('sse-dot--connected');
    expect(html).toContain('Live');
  });

  test('reconnecting state contains attempt info', () => {
    const html = buildStatusHTML('reconnecting', { reconnectAttempt: 3, maxReconnectAttempts: 10 });
    expect(html).toContain('sse-dot--reconnecting');
    expect(html).toContain('Reconnecting (3/10)');
  });

  test('reconnecting without max shows simple label', () => {
    const html = buildStatusHTML('reconnecting', {});
    expect(html).toContain('Reconnecting…');
  });

  test('disconnected state contains last updated time', () => {
    const ts = Date.now() - 60000;
    const html = buildStatusHTML('disconnected', { lastEventTime: ts });
    expect(html).toContain('sse-dot--disconnected');
    expect(html).toContain('Disconnected');
    expect(html).toContain('1m ago');
  });

  test('disconnected without lastEventTime shows no time', () => {
    const html = buildStatusHTML('disconnected', {});
    expect(html).toContain('Disconnected');
    expect(html).not.toContain('Last updated');
  });

  test('unknown state returns empty string', () => {
    expect(buildStatusHTML('unknown')).toBe('');
  });
});

describe('SSEStatusIndicator', () => {
  let element;

  beforeEach(() => {
    element = document.createElement('div');
    element.id = 'sse-status';
    document.body.appendChild(element);
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  test('constructor sets aria attributes', () => {
    const indicator = new SSEStatusIndicator('sse-status');
    expect(element.getAttribute('role')).toBe('status');
    expect(element.getAttribute('aria-live')).toBe('polite');
    expect(element.classList.contains('sse-status')).toBe(true);
  });

  test('constructor accepts element directly', () => {
    const indicator = new SSEStatusIndicator(element);
    expect(indicator.element).toBe(element);
  });

  test('setConnected shows element and renders connected state', () => {
    const indicator = new SSEStatusIndicator('sse-status');
    element.classList.add('hidden');
    indicator.setConnected();
    expect(element.classList.contains('hidden')).toBe(false);
    expect(element.innerHTML).toContain('Live');
  });

  test('setReconnecting renders reconnecting with attempt info', () => {
    const indicator = new SSEStatusIndicator('sse-status');
    indicator.setReconnecting(5, 10);
    expect(element.innerHTML).toContain('Reconnecting (5/10)');
  });

  test('setDisconnected renders disconnected with last updated', () => {
    const indicator = new SSEStatusIndicator('sse-status');
    const ts = Date.now() - 30000;
    indicator.setDisconnected(ts);
    expect(element.innerHTML).toContain('Disconnected');
    expect(element.innerHTML).toContain('30s ago');
  });

  test('recordEvent updates lastEventTime', () => {
    const indicator = new SSEStatusIndicator('sse-status');
    const ts = Date.now() - 5000;
    indicator.recordEvent(ts);
    expect(indicator.lastEventTime).toBe(ts);
  });

  test('recordEvent transitions from disconnected to connected', () => {
    const indicator = new SSEStatusIndicator('sse-status');
    indicator.setDisconnected(Date.now() - 60000);
    expect(indicator.currentState).toBe('disconnected');
    indicator.recordEvent();
    expect(indicator.currentState).toBe('connected');
    expect(element.innerHTML).toContain('Live');
  });

  test('hide adds hidden class', () => {
    const indicator = new SSEStatusIndicator('sse-status');
    indicator.setConnected();
    indicator.hide();
    expect(element.classList.contains('hidden')).toBe(true);
  });

  test('show removes hidden class', () => {
    const indicator = new SSEStatusIndicator('sse-status');
    element.classList.add('hidden');
    indicator.show();
    expect(element.classList.contains('hidden')).toBe(false);
  });

  test('handles missing element gracefully', () => {
    const indicator = new SSEStatusIndicator('nonexistent-id');
    expect(() => indicator.setConnected()).not.toThrow();
    expect(() => indicator.setReconnecting(1, 10)).not.toThrow();
    expect(() => indicator.setDisconnected(0)).not.toThrow();
    expect(() => indicator.hide()).not.toThrow();
  });
});
