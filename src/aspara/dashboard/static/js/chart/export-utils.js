/**
 * Pure utility functions for chart export
 * These functions have no side effects and are easy to test
 */

/**
 * Generate CSV content from series data (SoA format)
 * @param {Array} series - Array of series objects with name and data in SoA format
 * @returns {string} CSV formatted string
 */
export function generateCSVContent(series) {
  const lines = ['series,step,value'];

  for (const s of series) {
    if (!s.data?.steps?.length) continue;
    const { steps, values } = s.data;

    const seriesName = s.name.replace(/"/g, '""');

    for (let i = 0; i < steps.length; i++) {
      lines.push(`"${seriesName}",${steps[i]},${values[i]}`);
    }
  }

  return `${lines.join('\n')}\n`;
}

/**
 * Sanitize a string for use as a filename
 * @param {string} name - Original name
 * @returns {string} Sanitized filename
 */
export function sanitizeFileName(name) {
  return name.replace(/[^a-z0-9]/gi, '_').toLowerCase();
}

/**
 * Get export filename from chart data
 * @param {Object} data - Chart data object with optional title and series
 * @returns {string} Filename without extension
 */
export function getExportFileName(data) {
  if (data.title) {
    return sanitizeFileName(data.title);
  }
  if (data.series && data.series.length === 1) {
    return sanitizeFileName(data.series[0].name);
  }
  return 'chart';
}

/**
 * Calculate dimensions for zoomed/unzoomed export
 * @param {Object} chart - Chart object with zoom, width, height, and MARGIN
 * @returns {Object} Dimensions info including useZoomedArea, margin, plotWidth, plotHeight
 */
export function calculateExportDimensions(chart) {
  const useZoomedArea = chart.zoom.x !== null || chart.zoom.y !== null;
  const margin = chart.constructor.MARGIN;
  const plotWidth = chart.width - margin * 2;
  const plotHeight = chart.height - margin * 2;

  return { useZoomedArea, margin, plotWidth, plotHeight };
}

/**
 * Build filename with optional zoom suffix
 * @param {string} baseName - Base filename
 * @param {boolean} isZoomed - Whether to add zoomed suffix
 * @returns {string} Final filename
 */
export function buildExportFileName(baseName, isZoomed) {
  return isZoomed ? `${baseName}_zoomed` : baseName;
}
