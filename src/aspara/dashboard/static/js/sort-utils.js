/**
 * Shared sort header listener utilities for list pages.
 */

/**
 * Attach click listeners to all [data-sort] headers and update sort state.
 *
 * The instance is expected to expose `sortKey`, `sortOrder`,
 * `updateSortIndicators()`, and `sortAndRender()`.
 *
 * @param {Object} instance - The list sorter instance
 * @param {string} storagePrefix - Prefix for localStorage keys (e.g. 'projects')
 * @param {AbortSignal|null} signal - Optional AbortSignal for automatic cleanup
 * @returns {Array<{element: HTMLElement, handler: function}>} Registered handlers
 */
export function attachSortHeaders(instance, storagePrefix, signal = null) {
  const handlers = [];
  const headers = document.querySelectorAll('[data-sort]');
  for (const header of headers) {
    const handler = () => {
      const key = header.dataset.sort;
      if (instance.sortKey === key) {
        instance.sortOrder = instance.sortOrder === 'asc' ? 'desc' : 'asc';
      } else {
        instance.sortKey = key;
        instance.sortOrder = 'asc';
      }
      localStorage.setItem(`${storagePrefix}_sort_key`, instance.sortKey);
      localStorage.setItem(`${storagePrefix}_sort_order`, instance.sortOrder);
      instance.updateSortIndicators();
      instance.sortAndRender();
    };
    const options = signal ? { signal } : {};
    header.addEventListener('click', handler, options);
    handlers.push({ element: header, handler });
  }
  return handlers;
}
