/**
 * Y-axis scaling utilities for the canvas chart.
 *
 * Centralizes mapping between data values and canvas coordinates for
 * linear and logarithmic scales so that rendering, interaction, and zoom
 * all use the same transformation (SSOT).
 */

export const YScale = Object.freeze({
  LINEAR: 'linear',
  LOG: 'log',
});

const LOG_10 = Math.log(10);

/**
 * Check whether a scale is logarithmic.
 * @param {string} scale
 * @returns {boolean}
 */
export function isLogScale(scale) {
  return scale === YScale.LOG;
}

/**
 * Values that can be plotted on a true log scale must be strictly positive.
 * @param {number} value
 * @returns {boolean}
 */
export function isValidLogValue(value) {
  return Number.isFinite(value) && value > 0;
}

/**
 * Convert a data value to its base-10 logarithm.
 * @param {number} value
 * @returns {number}
 */
export function toLogDomain(value) {
  return Math.log(value) / LOG_10;
}

/**
 * Convert a base-10 logarithm back to the data domain.
 * @param {number} logValue
 * @returns {number}
 */
export function fromLogDomain(logValue) {
  return 10 ** logValue;
}

/**
 * Compute the padded y-axis range used for drawing.
 *
 * For linear scales padding is applied in data space. For log scales padding
 * is applied in log space so that the visual margin stays proportional on
 * a logarithmic axis.
 *
 * @param {number} yMin - Data-space minimum
 * @param {number} yMax - Data-space maximum
 * @param {string} scale - YScale value
 * @param {number} paddingRatio - Fraction of the range to pad
 * @returns {{ yMinPadded: number, yMaxPadded: number }}
 */
export function computePaddedYRange(yMin, yMax, scale, paddingRatio) {
  if (isLogScale(scale)) {
    if (yMin <= 0 || yMax <= 0) {
      throw new Error('Log scale requires positive yMin and yMax');
    }
    let logMin = toLogDomain(yMin);
    let logMax = toLogDomain(yMax);
    let logRange = logMax - logMin;
    if (logRange === 0) {
      // All values are identical; give a default 1-decade range so the line
      // still renders horizontally in the middle of the plot.
      logRange = 1;
      logMin -= 0.5;
      logMax += 0.5;
    }
    const paddedLogMin = logMin - logRange * paddingRatio;
    const paddedLogMax = logMax + logRange * paddingRatio;
    return {
      yMinPadded: fromLogDomain(paddedLogMin),
      yMaxPadded: fromLogDomain(paddedLogMax),
    };
  }

  const yRange = yMax - yMin;
  if (yRange === 0) {
    // Avoid degenerate zero-range axes.
    return { yMinPadded: yMin - 1, yMaxPadded: yMax + 1 };
  }
  return {
    yMinPadded: yMin - yRange * paddingRatio,
    yMaxPadded: yMax + yRange * paddingRatio,
  };
}

/**
 * Map a data value to a canvas y-coordinate.
 *
 * @param {number} value
 * @param {string} scale - YScale value
 * @param {number} plotHeight
 * @param {number} margin
 * @param {number} yMinPadded
 * @param {number} yMaxPadded
 * @returns {number}
 */
export function valueToChartY(value, scale, plotHeight, margin, yMinPadded, yMaxPadded) {
  if (isLogScale(scale)) {
    const logValue = toLogDomain(value);
    const logMin = toLogDomain(yMinPadded);
    const logMax = toLogDomain(yMaxPadded);
    const ratio = (logValue - logMin) / (logMax - logMin);
    return margin + plotHeight - ratio * plotHeight;
  }
  const ratio = (value - yMinPadded) / (yMaxPadded - yMinPadded);
  return margin + plotHeight - ratio * plotHeight;
}

/**
 * Map a canvas y-coordinate back to a data value.
 *
 * @param {number} y
 * @param {string} scale - YScale value
 * @param {number} plotHeight
 * @param {number} margin
 * @param {number} yMinPadded
 * @param {number} yMaxPadded
 * @returns {number}
 */
export function chartYToValue(y, scale, plotHeight, margin, yMinPadded, yMaxPadded) {
  const ratio = (plotHeight - (y - margin)) / plotHeight;
  if (isLogScale(scale)) {
    const logMin = toLogDomain(yMinPadded);
    const logMax = toLogDomain(yMaxPadded);
    return fromLogDomain(logMin + ratio * (logMax - logMin));
  }
  return yMinPadded + ratio * (yMaxPadded - yMinPadded);
}

/**
 * Format a tick value for a logarithmic axis.
 *
 * Uses plain decimal notation for values from 0.01 up to large integers, and
 * exponential notation for very small values, matching the wandb/TensorBoard
 * convention for readability.
 *
 * @param {number} value
 * @returns {string}
 */
export function formatLogTick(value) {
  const abs = Math.abs(value);
  if (abs === 0) return '0';
  if (abs >= 0.01) return value.toString();
  return value.toExponential(1).replace(/\.0/, '');
}

/**
 * Generate major tick positions for a logarithmic axis.
 *
 * Ticks are placed at powers of ten within the requested range. If no full
 * power of ten falls inside the range, the endpoints are used as a fallback.
 *
 * @param {number} yMin
 * @param {number} yMax
 * @param {number} [maxTicks=10]
 * @returns {Array<{ value: number, label: string }>}
 */
export function generateLogTicks(yMin, yMax, maxTicks = 10) {
  const logMin = Math.ceil(toLogDomain(yMin));
  const logMax = Math.floor(toLogDomain(yMax));
  const ticks = [];
  for (let exponent = logMin; exponent <= logMax; exponent++) {
    const value = fromLogDomain(exponent);
    ticks.push({ value, label: formatLogTick(value) });
  }
  if (ticks.length === 0) {
    ticks.push(
      { value: yMin, label: formatLogTick(yMin) },
      { value: yMax, label: formatLogTick(yMax) },
    );
  }
  if (ticks.length > maxTicks) {
    const step = Math.ceil(ticks.length / maxTicks);
    return ticks.filter((_, index) => index % step === 0);
  }
  return ticks;
}
