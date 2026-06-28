/**
 * SSE Status Updates for Runs List Page
 * Handles real-time status updates for runs displayed in the runs list
 */

import { INITIAL_SINCE_TIMESTAMP, buildSSEUrl, extractRunNamesFromElements, isConnectionClosed, parseStatusUpdate, updateRunStatusIcon } from './sse-utils.js';

class RunsListSSE {
  constructor(project) {
    this.project = project;
    this.eventSource = null;
    this.lastTimestamp = INITIAL_SINCE_TIMESTAMP;
    this.runs = [];

    // SSE event handlers (stored for cleanup)
    this.sseOpenHandler = null;
    this.sseStatusHandler = null;
    this.sseMetricHandler = null;
    this.sseErrorHandler = null;

    // Reconnection state — exponential backoff aligned with
    // metrics-data-service.js to avoid reconnection storms when the
    // server is down for an extended period.
    this.isReconnecting = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.baseReconnectDelay = 1000;

    this.setupSSE();
  }

  setupSSE() {
    const runElements = document.querySelectorAll('[data-run]');
    if (runElements.length === 0) {
      console.log('[RunsListSSE] No runs found on page');
      return;
    }

    this.runs = extractRunNamesFromElements(runElements);
    const sseUrl = buildSSEUrl(this.project, this.runs, this.lastTimestamp);
    console.log('[RunsListSSE] Connecting to SSE:', sseUrl);

    this.eventSource = new EventSource(sseUrl);

    // Store handlers as member variables for cleanup
    this.sseOpenHandler = () => {
      console.log('[RunsListSSE] SSE connection opened with since:', this.lastTimestamp);
      // Reset reconnection state on successful connection.
      this.isReconnecting = false;
      this.reconnectAttempts = 0;
      // Note: Don't update lastTimestamp here - it's updated when receiving events
      // This ensures we don't miss data between the last event and reconnection
    };

    this.sseStatusHandler = (event) => {
      const statusData = parseStatusUpdate(event.data);
      if (statusData === null) {
        return; // Skip invalid data
      }
      this.handleStatusUpdate(statusData);
      // Update lastTimestamp if the event has a timestamp
      if (statusData.timestamp) {
        this.lastTimestamp = statusData.timestamp;
      }
    };

    this.sseMetricHandler = (event) => {
      let metricData;
      try {
        metricData = JSON.parse(event.data);
      } catch (error) {
        console.error('[RunsListSSE] Error parsing metric JSON:', error);
        return;
      }
      // Update lastTimestamp if the event has a timestamp
      if (metricData?.timestamp) {
        this.lastTimestamp = metricData.timestamp;
      }
    };

    this.sseErrorHandler = (event) => {
      if (isConnectionClosed(this.eventSource.readyState)) {
        console.log('[RunsListSSE] SSE connection closed, attempting reconnect with since:', this.lastTimestamp);
        // Connection is closed, reconnect with updated timestamp
        this.reconnect();
      } else {
        console.error('[RunsListSSE] SSE connection error:', event);
      }
    };

    this.eventSource.addEventListener('open', this.sseOpenHandler);
    this.eventSource.addEventListener('status', this.sseStatusHandler);
    this.eventSource.addEventListener('metric', this.sseMetricHandler);
    this.eventSource.addEventListener('error', this.sseErrorHandler);
  }

  /**
   * Reconnect SSE with updated since timestamp.
   * Uses exponential backoff (1s, 2s, 4s, 8s... max 30s) and a max retry
   * limit to prevent reconnection storms when the server is down.
   */
  reconnect() {
    // Guard against concurrent reconnection attempts.
    if (this.isReconnecting) {
      console.log('[RunsListSSE] Already reconnecting, skipping');
      return;
    }

    // Check max retry count.
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[RunsListSSE] Max reconnection attempts reached, giving up');
      return;
    }

    this.isReconnecting = true;
    this.reconnectAttempts++;

    // Exponential backoff: 1s, 2s, 4s, 8s... (max 30s)
    const delay = Math.min(this.baseReconnectDelay * 2 ** (this.reconnectAttempts - 1), 30000);
    console.log(`[RunsListSSE] Reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}, waiting ${delay}ms`);

    // Close existing connection if any.
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    setTimeout(() => {
      if (this.runs.length > 0) {
        console.log('[RunsListSSE] Reconnecting SSE with since:', this.lastTimestamp);
        this.setupSSE();
      }
      // isReconnecting is reset in the 'open' handler on successful
      // connection. If runs is empty, reset here to avoid getting stuck.
      if (this.runs.length === 0) {
        this.isReconnecting = false;
      }
    }, delay);
  }

  handleStatusUpdate(statusData) {
    updateRunStatusIcon(statusData, '[RunsListSSE]');
  }

  close() {
    if (this.eventSource) {
      // Remove event listeners before closing to prevent memory leaks
      if (this.sseOpenHandler) {
        this.eventSource.removeEventListener('open', this.sseOpenHandler);
      }
      if (this.sseStatusHandler) {
        this.eventSource.removeEventListener('status', this.sseStatusHandler);
      }
      if (this.sseMetricHandler) {
        this.eventSource.removeEventListener('metric', this.sseMetricHandler);
      }
      if (this.sseErrorHandler) {
        this.eventSource.removeEventListener('error', this.sseErrorHandler);
      }
      this.eventSource.close();
      this.eventSource = null;
      console.log('[RunsListSSE] SSE connection closed manually');
    }
    this.sseOpenHandler = null;
    this.sseStatusHandler = null;
    this.sseMetricHandler = null;
    this.sseErrorHandler = null;
    // Reset reconnection state so a future re-init starts fresh.
    this.isReconnecting = false;
    this.reconnectAttempts = 0;
  }
}

window.RunsListSSE = RunsListSSE;

export { RunsListSSE };
