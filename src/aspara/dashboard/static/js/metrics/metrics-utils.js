/**
 * Metrics data processing utilities.
 * Pure functions for delta decompression and data transformation.
 */

/**
 * Decompress delta-compressed metrics data and keep SoA (Structure of Arrays) format.
 * Input array format: {steps: [delta...], values: [...], timestamps: [delta...]}
 * - steps and timestamps are delta-compressed (first value is absolute, rest are deltas)
 * Output SoA format: {steps: [...], values: [...], timestamps: [...]}
 *
 * @param {Object} arrayData - Delta-compressed metrics data {metric: {run: {steps, values, timestamps}}}
 * @returns {Object} Decompressed metrics data in SoA format
 */
export function decompressDeltaData(arrayData) {
  const result = {};

  for (const [metricName, runData] of Object.entries(arrayData)) {
    result[metricName] = {};

    for (const [runName, arrays] of Object.entries(runData)) {
      const length = arrays.steps.length;
      const steps = new Array(length);
      const timestamps = new Array(length);

      // Decompress delta-encoded arrays
      let step = 0;
      let timestamp_ms = 0;

      for (let i = 0; i < length; i++) {
        // Decode step (delta-compressed)
        step += arrays.steps[i];
        steps[i] = step;

        // Decode timestamp (delta-compressed, unix time in ms)
        timestamp_ms += arrays.timestamps[i];
        timestamps[i] = timestamp_ms;
      }

      result[metricName][runName] = {
        steps,
        values: arrays.values,
        timestamps,
      };
    }
  }

  return result;
}

/**
 * Convert metrics data to Chart.js compatible format.
 *
 * @param {string} metricName - Name of the metric
 * @param {Object} runData - Run data in SoA format { runName: { steps: [], values: [], timestamps: [] } }
 * @returns {Object} Chart data format { title: string, series: Array }
 */
export function convertToChartFormat(metricName, runData) {
  const series = [];

  for (const [runName, data] of Object.entries(runData)) {
    if (data?.steps?.length > 0) {
      series.push({
        name: runName,
        data: { steps: data.steps, values: data.values },
      });
    }
  }

  return {
    title: metricName,
    series: series,
  };
}

/**
 * Find the latest timestamp from metrics data.
 *
 * @param {Object} metricsData - Metrics data in SoA format {metric: {run: {steps, values, timestamps}}}
 * @returns {number} Latest timestamp in milliseconds, or 0 if no data
 */
export function findLatestTimestamp(metricsData) {
  let latestTimestamp = 0;

  for (const runData of Object.values(metricsData)) {
    for (const data of Object.values(runData)) {
      if (data.timestamps && data.timestamps.length > 0) {
        const lastTs = data.timestamps[data.timestamps.length - 1];
        if (lastTs > latestTimestamp) {
          latestTimestamp = lastTs;
        }
      }
    }
  }

  return latestTimestamp;
}

/**
 * Merge new data point into cached data using binary search for sorted insertion.
 *
 * @param {Object} cached - Cached data { steps: [], values: [], timestamps: [] }
 * @param {number} step - Step number
 * @param {number} value - Metric value
 * @param {number} timestamp - Timestamp in milliseconds
 */
export function mergeDataPoint(cached, step, value, timestamp) {
  // Binary search to find insertion point for sorted order by step
  let left = 0;
  let right = cached.steps.length;

  while (left < right) {
    const mid = (left + right) >> 1;
    if (cached.steps[mid] < step) {
      left = mid + 1;
    } else if (cached.steps[mid] > step) {
      right = mid;
    } else {
      // Step already exists - update the value in place
      cached.values[mid] = value;
      cached.timestamps[mid] = timestamp;
      return;
    }
  }

  // Insert at sorted position
  cached.steps.splice(left, 0, step);
  cached.values.splice(left, 0, value);
  cached.timestamps.splice(left, 0, timestamp);
}
