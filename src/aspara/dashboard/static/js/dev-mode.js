/**
 * Development mode utilities
 */

/**
 * Check if running in development mode.
 * @returns {boolean} true if dev mode is active
 */
export function isDev() {
  return document.body.hasAttribute('data-dev-mode');
}
