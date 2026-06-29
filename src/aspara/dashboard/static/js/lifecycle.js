/**
 * @file Lifecycle contract for all resource-holding frontend classes.
 *
 * Every class that owns long-lived resources (SSE connections, event
 * listeners, timers, child instances, etc.) must implement `destroy()`.
 *
 * The contract:
 * - `destroy()` MUST be idempotent (safe to call multiple times).
 * - `destroy()` MUST remove all event listeners added by the class.
 * - `destroy()` MUST close/stop any async resources (SSE, timers, etc.).
 * - `destroy()` MUST call `destroy()` on owned child instances.
 * - After `destroy()`, the instance should not be used again.
 *
 * Pure utility modules and stateless functions do not need to implement
 * this interface.
 */

/**
 * @typedef {Object} Destroyable
 * @property {function(): void} destroy - Release all resources held by this instance. Must be idempotent.
 */

/**
 * Register a pagehide listener that tears down a page on true unload
 * but preserves it when frozen into the back/forward cache (bfcache).
 *
 * When the browser freezes a page into bfcache (back/forward navigation),
 * `pagehide` fires with `event.persisted === true`. In that case the page
 * must keep its event listeners and resources intact so it works
 * immediately when restored from bfcache. Only call `destroy()` on a
 * real unload (`persisted === false`).
 *
 * Using `beforeunload` instead would call `destroy()` unconditionally,
 * stripping listeners before bfcache freezes the page — so after
 * restoration the page is inert (e.g. clicking a project card does
 * nothing). `pagehide` + `persisted` is the correct hook.
 *
 * @param {Destroyable} page - Page instance whose destroy() releases resources.
 * @returns {function(): void} Cleanup function to remove the listener (for tests).
 */
export function registerPageLifecycle(page) {
  const handler = (event) => {
    if (!event.persisted) {
      page.destroy();
    }
  };
  window.addEventListener('pagehide', handler);
  return () => window.removeEventListener('pagehide', handler);
}
