/**
 * SSE Status Indicator
 *
 * Displays the current SSE connection state (connected / reconnecting / disconnected)
 * so users can tell whether the data they are viewing is live or stale.
 */

/** @typedef {'connected' | 'reconnecting' | 'disconnected'} ConnectionState */

/**
 * Format a timestamp (ms) as a relative "x ago" string.
 * @param {number} timestamp - UNIX timestamp in milliseconds
 * @returns {string} Human-readable relative time
 */
export function formatRelativeTime(timestamp) {
  if (!timestamp || timestamp <= 0) return '';
  const diff = Date.now() - timestamp;
  if (diff < 5000) return 'just now';
  if (diff < 60000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  return `${Math.floor(diff / 3600000)}h ago`;
}

/**
 * Build the inner HTML for a given connection state.
 * Pure function — no DOM side effects.
 * @param {ConnectionState} state
 * @param {Object} [opts]
 * @param {number} [opts.reconnectAttempt]
 * @param {number} [opts.maxReconnectAttempts]
 * @param {number} [opts.lastEventTime] - UNIX ms of last received event
 * @returns {string} HTML string
 */
export function buildStatusHTML(state, opts = {}) {
  switch (state) {
    case 'connected':
      return `<span class="sse-dot sse-dot--connected" aria-hidden="true"></span><span class="sse-label">Live</span>`;
    case 'reconnecting': {
      const attempt = opts.reconnectAttempt ?? 0;
      const max = opts.maxReconnectAttempts ?? 0;
      const label = max > 0 ? `Reconnecting (${attempt}/${max})…` : 'Reconnecting…';
      return `<span class="sse-dot sse-dot--reconnecting" aria-hidden="true"></span><span class="sse-label">${label}</span>`;
    }
    case 'disconnected': {
      const last = formatRelativeTime(opts.lastEventTime ?? 0);
      const lastStr = last ? ` · Last updated ${last}` : '';
      return `<span class="sse-dot sse-dot--disconnected" aria-hidden="true"></span><span class="sse-label">Disconnected${lastStr}</span>`;
    }
    default:
      return '';
  }
}

/**
 * SSEStatusIndicator manages a DOM element that reflects the SSE connection state.
 *
 * The indicator is keyboard-accessible (role="status", aria-live="polite") and
 * uses both colour and text/shape to distinguish states.
 */
export class SSEStatusIndicator {
  /**
   * @param {string|HTMLElement} elementOrId - DOM element or its ID
   */
  constructor(elementOrId) {
    if (typeof elementOrId === 'string') {
      this.element = document.getElementById(elementOrId);
    } else {
      this.element = elementOrId;
    }

    if (this.element) {
      this.element.setAttribute('role', 'status');
      this.element.setAttribute('aria-live', 'polite');
      this.element.classList.add('sse-status');
    }

    /** @type {ConnectionState|null} */
    this.currentState = null;
    this.reconnectAttempt = 0;
    this.maxReconnectAttempts = 0;
    this.lastEventTime = 0;
  }

  /**
   * Set the indicator to the "connected" state.
   */
  setConnected() {
    this.currentState = 'connected';
    this._render();
  }

  /**
   * Set the indicator to the "reconnecting" state.
   * @param {number} attempt - Current reconnect attempt number
   * @param {number} max - Maximum reconnect attempts
   */
  setReconnecting(attempt, max) {
    this.currentState = 'reconnecting';
    this.reconnectAttempt = attempt;
    this.maxReconnectAttempts = max;
    this._render();
  }

  /**
   * Set the indicator to the "disconnected" state.
   * @param {number} lastEventTime - UNIX ms of the last received event
   */
  setDisconnected(lastEventTime) {
    this.currentState = 'disconnected';
    this.lastEventTime = lastEventTime;
    this._render();
  }

  /**
   * Record that an event was received (updates lastEventTime).
   * If currently disconnected, transitions back to connected.
   * @param {number} [timestamp] - UNIX ms; defaults to Date.now()
   */
  recordEvent(timestamp) {
    this.lastEventTime = timestamp ?? Date.now();
    if (this.currentState === 'disconnected') {
      this.setConnected();
    }
  }

  /**
   * Hide the indicator (for pages that don't use SSE).
   */
  hide() {
    if (this.element) {
      this.element.classList.add('hidden');
    }
  }

  /**
   * Show the indicator.
   */
  show() {
    if (this.element) {
      this.element.classList.remove('hidden');
    }
  }

  _render() {
    if (!this.element) return;
    this.show();
    const html = buildStatusHTML(this.currentState, {
      reconnectAttempt: this.reconnectAttempt,
      maxReconnectAttempts: this.maxReconnectAttempts,
      lastEventTime: this.lastEventTime,
    });
    this.element.innerHTML = html;
  }
}
