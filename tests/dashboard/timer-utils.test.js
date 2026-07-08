/**
 * Unit tests for shared timer utilities (debounce).
 */
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { SEARCH_DEBOUNCE_MS, debounce } from '../../src/aspara/dashboard/static/js/timer-utils.js';

describe('timer-utils', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  describe('SEARCH_DEBOUNCE_MS', () => {
    test('matches the debounce window used by search/filter inputs', () => {
      expect(SEARCH_DEBOUNCE_MS).toBe(300);
    });
  });

  describe('debounce', () => {
    test('does not invoke fn before the delay elapses', () => {
      const fn = vi.fn();
      const debounced = debounce(fn, 300);

      debounced('a');

      expect(fn).not.toHaveBeenCalled();

      vi.advanceTimersByTime(299);
      expect(fn).not.toHaveBeenCalled();

      vi.advanceTimersByTime(1);
      expect(fn).toHaveBeenCalledTimes(1);
      expect(fn).toHaveBeenCalledWith('a');
    });

    test('resets the timer on each subsequent call (trailing invocation)', () => {
      const fn = vi.fn();
      const debounced = debounce(fn, 300);

      debounced('a');
      vi.advanceTimersByTime(200);
      debounced('b');
      vi.advanceTimersByTime(200);

      // 400ms total but only 200ms since the last call -> not yet fired.
      expect(fn).not.toHaveBeenCalled();

      vi.advanceTimersByTime(100);
      expect(fn).toHaveBeenCalledTimes(1);
      expect(fn).toHaveBeenCalledWith('b');
    });

    test('uses SEARCH_DEBOUNCE_MS by default', () => {
      const fn = vi.fn();
      const debounced = debounce(fn);

      debounced();

      vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS - 1);
      expect(fn).not.toHaveBeenCalled();

      vi.advanceTimersByTime(1);
      expect(fn).toHaveBeenCalledTimes(1);
    });

    test('cancel() prevents a pending invocation', () => {
      const fn = vi.fn();
      const debounced = debounce(fn, 300);

      debounced();
      debounced.cancel();

      vi.advanceTimersByTime(1000);
      expect(fn).not.toHaveBeenCalled();
    });

    test('cancel() is safe to call when nothing is pending', () => {
      const fn = vi.fn();
      const debounced = debounce(fn, 300);

      expect(() => debounced.cancel()).not.toThrow();
    });

    test('cancel() allows the debounced fn to be reused afterwards', () => {
      const fn = vi.fn();
      const debounced = debounce(fn, 300);

      debounced('first');
      debounced.cancel();
      vi.advanceTimersByTime(1000);

      debounced('second');
      vi.advanceTimersByTime(300);

      expect(fn).toHaveBeenCalledTimes(1);
      expect(fn).toHaveBeenCalledWith('second');
    });
  });
});
