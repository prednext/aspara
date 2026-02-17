/**
 * Pure utility functions for projects list
 * These functions have no side effects and are easy to test
 */

/**
 * Check if a project matches the search query
 * @param {Object} project - Project object with name and tags
 * @param {string} query - Search query string
 * @returns {boolean} True if project matches the query
 */
export function matchesSearch(project, query) {
  if (!query) {
    return true;
  }

  const normalizedQuery = query.toLowerCase();

  if (project.name.toLowerCase().includes(normalizedQuery)) {
    return true;
  }

  if (Array.isArray(project.tags)) {
    for (const tag of project.tags) {
      if (tag.toLowerCase().includes(normalizedQuery)) {
        return true;
      }
    }
  }

  return false;
}

/**
 * Create a sort comparator function for projects
 * @param {string} sortKey - The key to sort by ('name', 'runCount', 'lastUpdate')
 * @param {string} sortOrder - Sort order ('asc' or 'desc')
 * @returns {Function} Comparator function for Array.sort()
 */
export function createSortComparator(sortKey, sortOrder) {
  return (a, b) => {
    let aVal;
    let bVal;

    switch (sortKey) {
      case 'name':
        aVal = a.name.toLowerCase();
        bVal = b.name.toLowerCase();
        break;
      case 'runCount':
        aVal = a.runCount;
        bVal = b.runCount;
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
 * Parse a project DOM element into a data object
 * @param {HTMLElement} element - DOM element with data attributes
 * @returns {Object} Parsed project data
 */
export function parseProjectElement(element) {
  return {
    element,
    name: element.dataset.project,
    runCount: Number.parseInt(element.dataset.runCount) || 0,
    lastUpdate: Number.parseInt(element.dataset.lastUpdate) || 0,
    tags: (element.dataset.tags || '')
      .split(' ')
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0),
  };
}
