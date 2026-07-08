/**
 * @file Timer-related utilities shared across the dashboard.
 *
 * Single source of truth for debounce timing used by search/filter inputs.
 */

/**
 * Default debounce delay (ms) for search/filter inputs.
 * Balances responsiveness against re-render cost on large lists.
 */
export const SEARCH_DEBOUNCE_MS = 300;

/**
 * Create a debounced wrapper around `fn` that delays invocation until `delay`
 * ms have elapsed since the last call. The wrapper exposes a `.cancel()`
 * method to clear any pending invocation (call it during teardown).
 *
 * @param {function(...*): void} fn - Function to debounce.
 * @param {number} [delay=SEARCH_DEBOUNCE_MS] - Debounce window in milliseconds.
 * @returns {{ (...*): void, cancel(): void }} Debounced function with `.cancel()`.
 */
export function debounce(fn, delay = SEARCH_DEBOUNCE_MS) {
  let timeoutId = null;

  function debounced(...args) {
    if (timeoutId !== null) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      timeoutId = null;
      fn(...args);
    }, delay);
  }

  debounced.cancel = () => {
    if (timeoutId !== null) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
  };

  return debounced;
}
