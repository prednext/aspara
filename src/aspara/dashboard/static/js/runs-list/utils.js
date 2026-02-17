/**
 * Pure utility functions for runs list
 * These functions have no side effects and are easy to test
 */

/**
 * Create a sort comparator function for runs
 * @param {string} sortKey - The key to sort by ('name', 'metricCount', 'paramCount', 'lastUpdate')
 * @param {string} sortOrder - Sort order ('asc' or 'desc')
 * @returns {Function} Comparator function for Array.sort()
 */
export function createRunSortComparator(sortKey, sortOrder) {
  return (a, b) => {
    let aVal;
    let bVal;

    switch (sortKey) {
      case 'name':
        aVal = a.name.toLowerCase();
        bVal = b.name.toLowerCase();
        break;
      case 'paramCount':
        aVal = a.paramCount;
        bVal = b.paramCount;
        break;
      case 'lastUpdate':
        aVal = a.lastUpdate;
        bVal = b.lastUpdate;
        break;
      default:
        return 0;
    }

    if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1;
    if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1;
    return 0;
  };
}

/**
 * Parse a run DOM element into a data object
 * @param {HTMLElement} element - DOM element with data attributes
 * @returns {Object} Parsed run data
 */
export function parseRunElement(element) {
  return {
    element,
    name: element.dataset.run,
    paramCount: Number.parseInt(element.dataset.paramCount) || 0,
    lastUpdate: Number.parseInt(element.dataset.lastUpdate) || 0,
  };
}
