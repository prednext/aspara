/**
 * Tests for registerPageLifecycle — the bfcache-safe teardown helper.
 *
 * Regression guard: previously each page registered `beforeunload` →
 * `destroy()`, which stripped event listeners before the browser froze
 * the page into the back/forward cache (bfcache). After restoration the
 * page was inert (e.g. clicking a project card did nothing). The fix
 * uses `pagehide` + `event.persisted` so destroy() only runs on a true
 * unload, not on bfcache freeze.
 */
import { afterEach, describe, expect, test, vi } from 'vitest';

import { registerPageLifecycle } from '../../src/aspara/dashboard/static/js/lifecycle.js';

describe('registerPageLifecycle', () => {
  let cleanup;

  afterEach(() => {
    if (cleanup) {
      cleanup();
      cleanup = null;
    }
  });

  test('calls destroy() on pagehide with persisted=false (true unload)', () => {
    const page = { destroy: vi.fn() };
    cleanup = registerPageLifecycle(page);

    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: false }));

    expect(page.destroy).toHaveBeenCalledTimes(1);
  });

  test('does NOT call destroy() on pagehide with persisted=true (bfcache freeze)', () => {
    const page = { destroy: vi.fn() };
    cleanup = registerPageLifecycle(page);

    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }));

    expect(page.destroy).not.toHaveBeenCalled();
  });

  test('does NOT call destroy() on beforeunload (must use pagehide instead)', () => {
    const page = { destroy: vi.fn() };
    cleanup = registerPageLifecycle(page);

    window.dispatchEvent(new Event('beforeunload'));

    expect(page.destroy).not.toHaveBeenCalled();
  });

  test('survives repeated bfcache freeze/restore cycles then destroys on real unload', () => {
    const page = { destroy: vi.fn() };
    cleanup = registerPageLifecycle(page);

    // Simulate: freeze → restore → freeze → restore → real unload
    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }));
    window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }));
    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }));
    window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true }));
    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: false }));

    expect(page.destroy).toHaveBeenCalledTimes(1);
  });

  test('returned cleanup function removes the listener', () => {
    const page = { destroy: vi.fn() };
    cleanup = registerPageLifecycle(page);

    cleanup();
    cleanup = null;

    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: false }));

    expect(page.destroy).not.toHaveBeenCalled();
  });
});
