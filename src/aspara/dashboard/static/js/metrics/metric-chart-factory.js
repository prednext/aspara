/**
 * Metric chart DOM factory.
 * Creates chart container elements for metrics visualization.
 */
import { escapeHtml } from '../html-utils.js';

/**
 * Create a metric chart container element.
 *
 * @param {string} metricName - Name of the metric
 * @param {number} chartHeight - Height of the chart in pixels
 * @param {string} [chartSize='M'] - Chart size ('S', 'M', or 'L') for padding adjustment
 * @returns {{ container: HTMLElement, chartDiv: HTMLElement, chartId: string }}
 */
export function createMetricChartContainer(metricName, chartHeight, chartSize = 'M') {
  const chartContainer = document.createElement('div');
  // Use smaller padding for S size to maximize chart area
  const padding = chartSize === 'S' ? 'p-3' : 'p-6';
  chartContainer.className = `bg-base-surface border border-base-border ${padding}`;

  const chartId = `chart-${metricName.replace(/[^a-zA-Z0-9]/g, '_')}`;

  // Header section
  const chartHeader = document.createElement('div');
  chartHeader.className = 'flex items-center justify-between mb-6';

  const chartTitle = document.createElement('h3');
  chartTitle.className = 'text-sm font-semibold text-text-primary uppercase tracking-wider';
  chartTitle.textContent = metricName;
  chartHeader.appendChild(chartTitle);

  chartContainer.appendChild(chartHeader);

  // Chart div - use inline style for height to ensure it's set before Chart initialization
  const chartDiv = document.createElement('div');
  chartDiv.id = chartId;
  chartDiv.className = 'bg-base-bg';
  chartDiv.style.height = `${chartHeight}px`;
  chartDiv.style.width = '100%';
  chartDiv.style.boxSizing = 'border-box';
  chartContainer.appendChild(chartDiv);

  return { container: chartContainer, chartDiv, chartId };
}

/**
 * Create an error display for a failed chart.
 *
 * @param {string} metricName - Name of the metric
 * @param {string} errorMessage - Error message to display
 * @returns {HTMLElement}
 */
export function createChartErrorDisplay(metricName, errorMessage) {
  const container = document.createElement('div');
  container.className = 'bg-base-surface border border-base-border p-6';
  container.innerHTML = `
    <h3 class="text-sm font-semibold text-text-primary uppercase tracking-wider mb-6">${escapeHtml(metricName)}</h3>
    <div class="text-status-error p-4">Error creating chart: ${escapeHtml(errorMessage)}</div>
  `;
  return container;
}
