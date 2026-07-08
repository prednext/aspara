/**
 * SSE reconnection state manager.
 *
 * Single source of truth for reconnection constants, exponential backoff
 * calculation, reconnection guard logic, and connection state notification.
 *
 * Used by both MetricsDataService and RunsListSSE to ensure consistent
 * reconnection behavior across all SSE consumers.
 */

/**
 * @typedef {'connected' | 'reconnecting' | 'disconnected'} ConnectionState
 */

/**
 * @typedef {Object} SSEReconnectManagerOptions
 * @property {function(ConnectionState, Object): void} [onConnectionStateChange]
 *   Callback invoked when the connection state changes.
 * @property {number} [maxReconnectAttempts]
 *   Maximum number of reconnection attempts before giving up.
 * @property {number} [baseReconnectDelay]
 *   Base delay in milliseconds for the first reconnection attempt.
 * @property {number} [maxReconnectDelay]
 *   Upper bound for the backoff delay in milliseconds.
 */

export class SSEReconnectManager {
  /** @type {number} Maximum reconnection attempts before giving up. */
  static MAX_RECONNECT_ATTEMPTS = 10;

  /** @type {number} Base delay (ms) for the first reconnection attempt. */
  static BASE_RECONNECT_DELAY_MS = 1000;

  /** @type {number} Upper bound for the backoff delay (ms). */
  static MAX_RECONNECT_DELAY_MS = 30000;

  /**
   * @param {SSEReconnectManagerOptions} [options]
   */
  constructor(options = {}) {
    this.onConnectionStateChange = options.onConnectionStateChange || null;
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? SSEReconnectManager.MAX_RECONNECT_ATTEMPTS;
    this.baseReconnectDelay = options.baseReconnectDelay ?? SSEReconnectManager.BASE_RECONNECT_DELAY_MS;
    this.maxReconnectDelay = options.maxReconnectDelay ?? SSEReconnectManager.MAX_RECONNECT_DELAY_MS;

    this.isReconnecting = false;
    this.reconnectAttempts = 0;
  }

  /**
   * Calculate exponential backoff delay for the given attempt number.
   *
   * @param {number} attempt - 1-based attempt number
   * @returns {number} Delay in milliseconds
   */
  calculateBackoffDelay(attempt) {
    return Math.min(this.baseReconnectDelay * 2 ** (attempt - 1), this.maxReconnectDelay);
  }

  /**
   * Check whether a new reconnection attempt is allowed.
   *
   * Returns false if a reconnection is already in progress or if the
   * maximum number of attempts has been reached. The caller is
   * responsible for emitting a 'disconnected' notification with
   * appropriate detail when the max is reached.
   *
   * @returns {boolean} True if a new reconnection attempt may proceed.
   */
  canReconnect() {
    if (this.isReconnecting) {
      return false;
    }
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      return false;
    }
    return true;
  }

  /**
   * Begin a reconnection attempt.
   *
   * Sets `isReconnecting` to true, increments `reconnectAttempts`, and
   * emits a 'reconnecting' state notification with attempt details.
   */
  beginReconnect() {
    this.isReconnecting = true;
    this.reconnectAttempts++;
    this.notifyConnectionState('reconnecting', {
      attempt: this.reconnectAttempts,
      max: this.maxReconnectAttempts,
    });
  }

  /**
   * Reset reconnection state after a successful connection.
   */
  resetReconnectState() {
    this.isReconnecting = false;
    this.reconnectAttempts = 0;
  }

  /**
   * Notify a connection state change via the registered callback.
   *
   * @param {ConnectionState} state
   * @param {Object} [detail={}] - Additional context
   */
  notifyConnectionState(state, detail = {}) {
    if (this.onConnectionStateChange) {
      this.onConnectionStateChange(state, detail);
    }
  }
}
