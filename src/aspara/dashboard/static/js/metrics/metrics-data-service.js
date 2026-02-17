/**
 * Metrics data service.
 * Handles API calls, caching, and SSE for real-time updates.
 */
import { decode as msgpackDecode } from '@msgpack/msgpack';
import { INITIAL_SINCE_TIMESTAMP, buildSSEUrl } from '../runs-list/sse-utils.js';
import { decompressDeltaData, findLatestTimestamp, mergeDataPoint } from './metrics-utils.js';

/**
 * MetricsDataService handles fetching, caching, and real-time updates for metrics data.
 */
export class MetricsDataService {
  // Cache constants
  static MIN_CACHE_SIZE = 3;
  static DEFAULT_MAX_CACHE_SIZE = 3;

  /**
   * @param {string} project - Project name
   * @param {Object} options - Configuration options
   * @param {function} options.onMetricUpdate - Callback when metric is updated via SSE
   * @param {function} options.onStatusUpdate - Callback when run status is updated via SSE
   * @param {function} options.onCacheUpdated - Callback when cache is updated (for re-rendering)
   */
  constructor(project, options = {}) {
    this.project = project;
    this.onMetricUpdate = options.onMetricUpdate || null;
    this.onStatusUpdate = options.onStatusUpdate || null;
    this.onCacheUpdated = options.onCacheUpdated || null;

    // Cache mechanism: metric-first format {metric: {run: data}}
    this.metricsCache = {};
    // Track which runs are cached
    this.cachedRuns = new Set();
    // LRU cache management: track access order with O(1) lookup
    this.cacheAccessOrder = [];
    this.cacheAccessSet = new Set();
    this.minCacheSize = MetricsDataService.MIN_CACHE_SIZE;
    this.maxCacheSize = MetricsDataService.DEFAULT_MAX_CACHE_SIZE;

    // SSE state
    this.eventSource = null;
    this.lastSSETimestamp = INITIAL_SINCE_TIMESTAMP;
    this.currentSSERuns = '';
    this.isReconnecting = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.baseReconnectDelay = 1000;

    // SSE event handlers (stored for cleanup)
    this.sseOpenHandler = null;
    this.sseMetricHandler = null;
    this.sseStatusHandler = null;
    this.sseErrorHandler = null;
  }

  /**
   * Adjust cache size to accommodate selected runs.
   * @param {number} selectedCount - Number of selected runs
   */
  adjustCacheSize(selectedCount) {
    this.maxCacheSize = Math.max(this.minCacheSize, selectedCount);
  }

  /**
   * Check which runs need to be fetched (not in cache).
   * @param {Set<string>} runNames - Set of run names
   * @returns {Array<string>} Array of run names that need to be fetched
   */
  getRunsToFetch(runNames) {
    const toFetch = [];
    for (const runName of runNames) {
      if (!this.cachedRuns.has(runName)) {
        toFetch.push(runName);
      }
    }
    return toFetch;
  }

  /**
   * Fetch metrics for specific runs and add to cache.
   * @param {Array<string>} runNames - Array of run names to fetch
   * @returns {Promise<void>}
   */
  async fetchAndCacheMetrics(runNames) {
    const runsList = runNames.join(',');

    const fetchStart = performance.now();
    const response = await fetch(`/api/projects/${encodeURIComponent(this.project)}/runs/metrics?runs=${encodeURIComponent(runsList)}&format=msgpack`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    // Decode MessagePack binary response
    const arrayBuffer = await response.arrayBuffer();
    const data = msgpackDecode(arrayBuffer);
    const fetchEnd = performance.now();
    const fetchTime = fetchEnd - fetchStart;

    if (data.error) {
      throw new Error(data.error);
    }

    console.log(`📊 [Performance] API fetch time (MessagePack): ${fetchTime.toFixed(2)}ms`);

    // Decompress delta-compressed data (keep SoA format)
    const convertedData = decompressDeltaData(data.metrics);

    // Store converted data in cache (run-by-run)
    this.cacheMetricsData(convertedData, runNames);

    // Update lastSSETimestamp with the latest timestamp from fetched data
    const latestTimestamp = findLatestTimestamp(convertedData);
    if (latestTimestamp > this.lastSSETimestamp) {
      this.lastSSETimestamp = latestTimestamp;
      console.log('[SSE] Updated lastSSETimestamp from API data:', this.lastSSETimestamp);
    }

    // Setup SSE for real-time updates
    this.setupSSE(runsList);
  }

  /**
   * Get cached metrics for selected runs.
   * @param {Set<string>} selectedRuns - Set of selected run names
   * @returns {Object} Filtered metrics data in metric-first format
   */
  getCachedMetrics(selectedRuns) {
    const metricsData = {};

    for (const [metricName, runData] of Object.entries(this.metricsCache)) {
      const filteredRunData = {};
      for (const [runName, data] of Object.entries(runData)) {
        if (selectedRuns.has(runName)) {
          filteredRunData[runName] = data;
          // Update access order for selected runs
          this.updateCacheAccess(runName);
        }
      }
      if (Object.keys(filteredRunData).length > 0) {
        metricsData[metricName] = filteredRunData;
      }
    }

    return metricsData;
  }

  /**
   * Update LRU cache access order.
   * Uses Set for O(1) existence check instead of O(n) indexOf.
   * @param {string} runName - Run name to mark as accessed
   */
  updateCacheAccess(runName) {
    if (this.cacheAccessSet.has(runName)) {
      // Remove from current position - O(n) but only when item exists
      const index = this.cacheAccessOrder.indexOf(runName);
      if (index > -1) {
        this.cacheAccessOrder.splice(index, 1);
      }
    } else {
      this.cacheAccessSet.add(runName);
    }
    this.cacheAccessOrder.push(runName);
  }

  /**
   * Evict least recently used runs if cache is over capacity.
   */
  evictLRU() {
    while (this.cachedRuns.size > this.maxCacheSize) {
      const oldestRun = this.cacheAccessOrder[0];
      if (!oldestRun) break;

      // Remove from all metrics
      for (const metricData of Object.values(this.metricsCache)) {
        delete metricData[oldestRun];
      }

      // Remove from tracking
      this.cachedRuns.delete(oldestRun);
      this.cacheAccessSet.delete(oldestRun);
      this.cacheAccessOrder.shift();
    }
  }

  /**
   * Cache metrics data in metric-first format.
   * @param {Object} metricsData - Metrics data in metric-first format {metric: {run: data}}
   * @param {Array<string>} runNames - Run names that were fetched
   */
  cacheMetricsData(metricsData, runNames) {
    // Merge new data into cache (metric-first format)
    for (const [metricName, runData] of Object.entries(metricsData)) {
      if (!this.metricsCache[metricName]) {
        this.metricsCache[metricName] = {};
      }
      for (const [runName, data] of Object.entries(runData)) {
        this.metricsCache[metricName][runName] = data;
      }
    }

    // Track cached runs and update LRU
    for (const runName of runNames) {
      this.cachedRuns.add(runName);
      this.updateCacheAccess(runName);
    }

    // Evict if over capacity
    this.evictLRU();
  }

  /**
   * Setup Server-Sent Events for real-time metric updates.
   * @param {string} runsList - Comma-separated list of run names
   */
  setupSSE(runsList) {
    this.closeSSE();
    this.currentSSERuns = runsList;

    const runsArray = runsList.split(',');
    const sseUrl = buildSSEUrl(this.project, runsArray, this.lastSSETimestamp);
    console.log('[SSE] Connecting with since:', this.lastSSETimestamp);
    this.eventSource = new EventSource(sseUrl);

    // Store handlers as member variables for cleanup
    this.sseOpenHandler = () => {
      console.log('[SSE] Connection opened with since:', this.lastSSETimestamp);
      // Reset reconnection state on successful connection
      this.isReconnecting = false;
      this.reconnectAttempts = 0;
    };

    this.sseMetricHandler = (event) => {
      try {
        const metric = JSON.parse(event.data);
        if (metric.timestamp) {
          const ts = new Date(metric.timestamp).getTime();
          if (!Number.isNaN(ts) && ts > this.lastSSETimestamp) {
            this.lastSSETimestamp = ts;
          }
        }
        this.handleMetricUpdate(metric);
      } catch (error) {
        console.error('Error processing SSE metric:', error);
      }
    };

    this.sseStatusHandler = (event) => {
      try {
        const statusData = JSON.parse(event.data);
        if (statusData.timestamp) {
          const ts = new Date(statusData.timestamp).getTime();
          if (!Number.isNaN(ts) && ts > this.lastSSETimestamp) {
            this.lastSSETimestamp = ts;
          }
        }
        if (this.onStatusUpdate) {
          this.onStatusUpdate(statusData);
        }
      } catch (error) {
        console.error('Error processing status update:', error);
      }
    };

    this.sseErrorHandler = () => {
      console.log('[SSE] Connection error, readyState:', this.eventSource.readyState);

      if (this.eventSource.readyState !== EventSource.CLOSED) {
        this.eventSource.close();
      }

      // Don't reset isReconnecting here - let reconnectSSE() manage the flag
      // This prevents concurrent reconnection attempts
      console.log('[SSE] Using custom reconnect with delta fetch, since:', this.lastSSETimestamp);
      this.reconnectSSE();
    };

    this.eventSource.addEventListener('open', this.sseOpenHandler);
    this.eventSource.addEventListener('metric', this.sseMetricHandler);
    this.eventSource.addEventListener('status', this.sseStatusHandler);
    this.eventSource.addEventListener('error', this.sseErrorHandler);
  }

  /**
   * Reconnect SSE with updated since timestamp.
   * Uses exponential backoff and max retry limit to prevent infinite loops.
   */
  async reconnectSSE() {
    if (this.isReconnecting) {
      console.log('[SSE] Already reconnecting, skipping');
      return;
    }

    // Check max retry count
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[SSE] Max reconnection attempts reached, giving up');
      this.isReconnecting = false;
      return;
    }

    this.isReconnecting = true;
    this.reconnectAttempts++;

    // Exponential backoff: 1s, 2s, 4s, 8s... (max 30s)
    const delay = Math.min(this.baseReconnectDelay * 2 ** (this.reconnectAttempts - 1), 30000);
    console.log(`[SSE] Reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}, waiting ${delay}ms`);

    try {
      if (this.eventSource) {
        this.eventSource.close();
        this.eventSource = null;
      }

      await new Promise((resolve) => setTimeout(resolve, delay));

      if (!this.currentSSERuns) {
        console.log('[SSE] No runs to reconnect');
        this.isReconnecting = false;
        return;
      }

      console.log('[SSE] Reconnecting - fetching delta since:', this.lastSSETimestamp);
      try {
        await this.fetchDeltaViaMsgPack(this.currentSSERuns);
      } catch (error) {
        console.error('[SSE] Failed to fetch delta:', error);
        // Continue to SSE connection even if delta fetch fails (data will sync on next fetch)
      }

      console.log('[SSE] Reconnecting SSE with since:', this.lastSSETimestamp);
      this.setupSSE(this.currentSSERuns);
      // Reset isReconnecting after setupSSE() completes
      // This allows the next error event to trigger a new reconnection attempt
      this.isReconnecting = false;
    } catch (error) {
      console.error('[SSE] Reconnection failed:', error);
      this.isReconnecting = false;
    }
  }

  /**
   * Fetch delta data via MessagePack API and merge into cache.
   * @param {string} runsList - Comma-separated list of run names
   */
  async fetchDeltaViaMsgPack(runsList) {
    const fetchStart = performance.now();
    const url = `/api/projects/${encodeURIComponent(this.project)}/runs/metrics?runs=${encodeURIComponent(runsList)}&format=msgpack&since=${this.lastSSETimestamp}`;

    console.log('[SSE] Fetching delta from:', url);

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const arrayBuffer = await response.arrayBuffer();
    const data = msgpackDecode(arrayBuffer);
    const fetchEnd = performance.now();

    if (data.error) {
      throw new Error(data.error);
    }

    console.log(`📊 [SSE Reconnect] Delta fetch time (MessagePack): ${(fetchEnd - fetchStart).toFixed(2)}ms`);

    const deltaData = decompressDeltaData(data.metrics);
    this.mergeDeltaIntoCache(deltaData);

    const latestTimestamp = findLatestTimestamp(deltaData);
    if (latestTimestamp > this.lastSSETimestamp) {
      this.lastSSETimestamp = latestTimestamp;
      console.log('[SSE] Updated lastSSETimestamp from delta:', this.lastSSETimestamp);
    }

    if (Object.keys(deltaData).length > 0 && this.onCacheUpdated) {
      console.log('[SSE] Re-rendering charts after delta merge');
      this.onCacheUpdated();
    }
  }

  /**
   * Merge delta data into existing cache.
   * @param {Object} deltaData - Delta data in metric-first format
   */
  mergeDeltaIntoCache(deltaData) {
    for (const [metricName, runData] of Object.entries(deltaData)) {
      if (!this.metricsCache[metricName]) {
        this.metricsCache[metricName] = {};
      }

      for (const [runName, newData] of Object.entries(runData)) {
        if (!this.cachedRuns.has(runName)) {
          continue;
        }

        if (!this.metricsCache[metricName][runName]) {
          this.metricsCache[metricName][runName] = newData;
          continue;
        }

        const cached = this.metricsCache[metricName][runName];
        for (let i = 0; i < newData.steps.length; i++) {
          mergeDataPoint(cached, newData.steps[i], newData.values[i], newData.timestamps[i]);
        }
      }
    }

    console.log('[SSE] Merged delta data into cache');
  }

  /**
   * Handle metric update from SSE.
   * @param {Object} metric - Metric record from SSE
   */
  handleMetricUpdate(metric) {
    console.log('[SSE] handleMetricUpdate called with:', metric);

    if (!metric.metrics || !metric.run) {
      console.warn('[SSE] Invalid metric - missing metrics or run:', metric);
      return;
    }

    const runName = metric.run;
    const step = metric.step || 0;
    const timestamp = metric.timestamp ? new Date(metric.timestamp).getTime() : Date.now();

    console.log(`[SSE] Processing metric: run=${runName}, step=${step}, metrics=${Object.keys(metric.metrics).join(',')}`);

    for (const [metricName, value] of Object.entries(metric.metrics)) {
      // Update cache (SoA format)
      if (this.cachedRuns.has(runName)) {
        if (!this.metricsCache[metricName]) {
          this.metricsCache[metricName] = {};
        }
        if (!this.metricsCache[metricName][runName]) {
          this.metricsCache[metricName][runName] = {
            steps: [],
            values: [],
            timestamps: [],
          };
        }
        const cached = this.metricsCache[metricName][runName];
        mergeDataPoint(cached, step, value, timestamp);
      }

      // Notify callback
      if (this.onMetricUpdate) {
        this.onMetricUpdate(metricName, runName, step, value);
      }
    }
  }

  /**
   * Close SSE connection.
   */
  closeSSE() {
    if (this.eventSource) {
      // Remove event listeners before closing to prevent memory leaks
      if (this.sseOpenHandler) {
        this.eventSource.removeEventListener('open', this.sseOpenHandler);
      }
      if (this.sseMetricHandler) {
        this.eventSource.removeEventListener('metric', this.sseMetricHandler);
      }
      if (this.sseStatusHandler) {
        this.eventSource.removeEventListener('status', this.sseStatusHandler);
      }
      if (this.sseErrorHandler) {
        this.eventSource.removeEventListener('error', this.sseErrorHandler);
      }
      this.eventSource.close();
      this.eventSource = null;
    }
    this.sseOpenHandler = null;
    this.sseMetricHandler = null;
    this.sseStatusHandler = null;
    this.sseErrorHandler = null;
    this.currentSSERuns = '';
  }

  /**
   * Destroy the service and clean up resources.
   */
  destroy() {
    this.closeSSE();
    this.metricsCache = {};
    this.cachedRuns.clear();
    this.cacheAccessOrder = [];
    this.cacheAccessSet.clear();
    this.reconnectAttempts = 0;
  }
}
