/**
 * Read-only mode guard
 * Shows a dialog when the user tries to edit in read-only mode.
 */

const isReadOnly = document.body.hasAttribute('data-read-only');

/**
 * Check if read-only mode is active and show dialog if so.
 * @returns {boolean} true if read-only mode is active (action should be blocked)
 */
export function guardReadOnly() {
  if (!isReadOnly) return false;
  document.getElementById('read-only-dialog')?.showModal();
  return true;
}
