/**
 * Pure utility functions for runs list SSE
 * These functions have no side effects and are easy to test
 */

/**
 * Initial timestamp for first SSE connection (epoch)
 * Using epoch ensures all existing data is fetched on first connection
 * Value is UNIX time in milliseconds
 */
export const INITIAL_SINCE_TIMESTAMP = 0;

/**
 * Build SSE URL for runs status stream
 * @param {string} project - Project name
 * @param {Array<string>} runs - Array of run names
 * @param {number} since - UNIX timestamp in milliseconds to filter metrics from (required)
 * @returns {string} SSE URL
 */
export function buildSSEUrl(project, runs, since) {
  const runsList = runs.join(',');
  return `/api/projects/${encodeURIComponent(project)}/runs/stream?runs=${encodeURIComponent(runsList)}&since=${since}`;
}

/**
 * Valid run status values
 */
const VALID_STATUSES = ['wip', 'completed', 'failed', 'maybe_failed'];

/**
 * Mapping from status to icon ID
 * Most statuses use the pattern status-icon-{status}, but some use shared icons
 */
const STATUS_ICON_MAP = {
  wip: 'status-icon-wip',
  completed: 'status-icon-completed',
  failed: 'status-icon-failed',
  maybe_failed: 'icon-exclamation-triangle',
};

/**
 * Parse status update from SSE event data
 * @param {string} eventData - JSON string from SSE event
 * @returns {Object|null} Parsed status data, or null if parsing or validation fails
 */
export function parseStatusUpdate(eventData) {
  try {
    const data = JSON.parse(eventData);

    // Validate required fields and types
    if (typeof data !== 'object' || data === null) {
      console.error('[SSE] Invalid status update: not an object');
      return null;
    }

    if (typeof data.run !== 'string' || data.run.length === 0) {
      console.error('[SSE] Invalid status update: missing or invalid run field');
      return null;
    }

    if (typeof data.status !== 'string' || !VALID_STATUSES.includes(data.status)) {
      console.error('[SSE] Invalid status update: invalid status value:', data.status);
      return null;
    }

    return data;
  } catch (e) {
    console.error('[SSE] Failed to parse status update:', e);
    return null;
  }
}

/**
 * Create icon update attributes from status data.
 * CSS styling is handled by the [data-status] attribute selector in CSS.
 * @param {Object} statusData - Status data with status (must be validated by parseStatusUpdate first)
 * @returns {Object} Icon update info with innerHTML, status
 */
export function createIconUpdateFromStatus(statusData) {
  // Validate status against whitelist (defense in depth)
  const status = VALID_STATUSES.includes(statusData.status) ? statusData.status : 'wip';
  const iconId = STATUS_ICON_MAP[status];
  return {
    innerHTML: `<svg class="w-4 h-4 flex-shrink-0"><use href="#${iconId}"></use></svg>`,
    status: status,
  };
}

/**
 * Extract run names from DOM elements
 * @param {NodeList|Array} elements - Elements with data-run attribute
 * @returns {Array<string>} Array of run names
 */
export function extractRunNamesFromElements(elements) {
  return Array.from(elements).map((el) => el.dataset.run);
}

/**
 * Check if EventSource connection is closed
 * @param {number} readyState - EventSource readyState
 * @returns {boolean} True if connection is closed
 */
export function isConnectionClosed(readyState) {
  // EventSource.CLOSED = 2
  return readyState === 2;
}

/**
 * Update run status icon in the DOM.
 * CSS styling is handled by the [data-status] attribute selector in CSS.
 * @param {Object} statusData - Status data with run, status
 * @param {string} logPrefix - Prefix for console logs (e.g., '[SSE]', '[RunsListSSE]')
 * @returns {boolean} True if update was successful, false if container not found
 */
export function updateRunStatusIcon(statusData, logPrefix = '[SSE]') {
  console.log(`${logPrefix} Status update:`, statusData);

  const runName = statusData.run;
  const container = document.querySelector(`[data-run-status-icon="${runName}"]`);

  if (container) {
    const update = createIconUpdateFromStatus(statusData);
    container.setAttribute('data-status', update.status);
    container.innerHTML = update.innerHTML;

    console.log(`${logPrefix} Updated status for run:`, runName);
    return true;
  }

  console.warn(`${logPrefix} Could not find status icon container for run:`, runName);
  return false;
}
