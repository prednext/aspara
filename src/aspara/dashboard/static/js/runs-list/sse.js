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
   * Reconnect SSE with updated since timestamp
   */
  reconnect() {
    // Close existing connection if any
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    // Delay reconnection slightly to avoid rapid reconnection loops
    setTimeout(() => {
      if (this.runs.length > 0) {
        console.log('[RunsListSSE] Reconnecting SSE with since:', this.lastTimestamp);
        this.setupSSE();
      }
    }, 1000);
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
  }
}

window.RunsListSSE = RunsListSSE;
