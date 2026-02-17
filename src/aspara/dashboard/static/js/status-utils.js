/**
 * Status utility functions for Aspara Dashboard.
 *
 * Provides display name mapping and status-related utilities.
 */

/**
 * Status display name mapping.
 * Maps status values to human-readable display names.
 */
export const STATUS_DISPLAY_NAMES = {
  wip: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  maybe_failed: 'Maybe Failed',
};

/**
 * Get display name for a status value.
 * @param {string} status - Status value (wip, completed, failed, maybe_failed)
 * @returns {string} Human-readable display name
 */
export function getStatusDisplayName(status) {
  return STATUS_DISPLAY_NAMES[status] || status;
}
