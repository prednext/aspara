/**
 * Pure utility functions for chart interaction
 * These functions have no side effects and are easy to test
 */

/**
 * Calculate data ranges from series data (SoA format)
 * @param {Array} series - Array of series objects with data in SoA format { steps: [], values: [] }
 * @returns {Object|null} Object with xMin, xMax, yMin, yMax or null if no data
 */
export function calculateDataRanges(series) {
  let xMin = Number.POSITIVE_INFINITY;
  let xMax = Number.NEGATIVE_INFINITY;
  let yMin = Number.POSITIVE_INFINITY;
  let yMax = Number.NEGATIVE_INFINITY;

  for (const s of series) {
    if (!s.data?.steps?.length) continue;
    const { steps, values } = s.data;

    // steps are sorted, so O(1) for min/max
    xMin = Math.min(xMin, steps[0]);
    xMax = Math.max(xMax, steps[steps.length - 1]);

    // values min/max
    for (let i = 0; i < values.length; i++) {
      if (values[i] < yMin) yMin = values[i];
      if (values[i] > yMax) yMax = values[i];
    }
  }

  return xMin === Number.POSITIVE_INFINITY ? null : { xMin, xMax, yMin, yMax };
}

/**
 * Binary search to find the nearest step in sorted steps array (SoA format)
 * @param {Array} steps - Sorted array of step values
 * @param {number} targetStep - Target step value
 * @returns {Object|null} Object with { index, step } or null if empty
 */
export function binarySearchNearestStep(steps, targetStep) {
  if (!steps?.length) return null;
  if (steps.length === 1) return { index: 0, step: steps[0] };

  let left = 0;
  let right = steps.length - 1;

  // Handle edge cases: target is outside data range
  if (targetStep <= steps[left]) return { index: left, step: steps[left] };
  if (targetStep >= steps[right]) return { index: right, step: steps[right] };

  // Binary search to find the two closest points
  while (left < right - 1) {
    const mid = (left + right) >> 1;
    if (steps[mid] <= targetStep) {
      left = mid;
    } else {
      right = mid;
    }
  }

  // Compare left and right to find nearest
  const leftDist = Math.abs(steps[left] - targetStep);
  const rightDist = Math.abs(steps[right] - targetStep);
  return leftDist <= rightDist ? { index: left, step: steps[left] } : { index: right, step: steps[right] };
}

/**
 * Binary search to find a point by step value (SoA format)
 * @param {Array} steps - Sorted array of step values
 * @param {Array} values - Array of values corresponding to steps
 * @param {number} step - Step value to find
 * @returns {Object|null} Object with { index, step, value } or null if not found
 */
export function binarySearchByStep(steps, values, step) {
  if (!steps?.length) return null;

  let left = 0;
  let right = steps.length - 1;

  while (left <= right) {
    const mid = (left + right) >> 1;
    if (steps[mid] === step) {
      return { index: mid, step: steps[mid], value: values[mid] };
    }
    if (steps[mid] < step) {
      left = mid + 1;
    } else {
      right = mid - 1;
    }
  }

  return null;
}

/**
 * Find the nearest step using binary search (SoA format, optimized version)
 * Handles LTTB downsampling where each series may have different steps.
 * @param {number} mouseX - Mouse X coordinate
 * @param {Array} series - Series data in SoA format (may have different steps per series due to LTTB)
 * @param {number} margin - Chart margin
 * @param {number} plotWidth - Plot width
 * @param {number} xMin - X axis minimum
 * @param {number} xMax - X axis maximum
 * @returns {number|null} Nearest step value or null
 */
export function findNearestStepBinary(mouseX, series, margin, plotWidth, xMin, xMax) {
  // Convert mouse X to target step value
  const targetStep = xMin + ((mouseX - margin) / plotWidth) * (xMax - xMin);

  let nearestStep = null;
  let minDistance = Number.POSITIVE_INFINITY;

  // Search each series for the nearest step (handles LTTB where series have different steps)
  // Complexity: O(N × log M) where N = series count, M = points per series
  for (const s of series) {
    if (!s.data?.steps?.length) continue;

    // Binary search to find nearest step in this series
    const result = binarySearchNearestStep(s.data.steps, targetStep);
    if (result === null) continue;

    const distance = Math.abs(result.step - targetStep);
    if (distance < minDistance) {
      minDistance = distance;
      nearestStep = result.step;
    }
  }

  return nearestStep;
}
