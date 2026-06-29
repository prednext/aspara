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
