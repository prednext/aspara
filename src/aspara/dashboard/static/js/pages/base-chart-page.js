import { escapeHtml } from '../html-utils.js';
/**
 * Base class for chart pages.
 * Provides common chart layout management functionality shared between
 * RunDetail and ProjectDetail pages.
 */
import {
  CHART_SIZE_KEY,
  applyGridLayout,
  calculateChartDimensions,
  updateChartHeights,
  updateContainerPadding,
  updateSizeButtonStyles,
} from '../metrics/chart-layout.js';
import { createChartErrorDisplay, createMetricChartContainer } from '../metrics/metric-chart-factory.js';

export { CHART_SIZE_KEY };

/**
 * BaseChartPage provides shared chart layout and sizing functionality.
 * Subclasses should set chartsContainer, chartControls, and size buttons
 * in their initializeElements() method.
 */
export class BaseChartPage {
  constructor() {
    this.charts = new Map();
    this.chartSize = localStorage.getItem(CHART_SIZE_KEY) || 'M';

    // These will be set by initializeElements()
    this.chartsContainer = null;
    this.chartControls = null;
    this.sizeSBtn = null;
    this.sizeMBtn = null;
    this.sizeLBtn = null;

    // Customizable properties (can be overridden by subclass before calling init methods)
    this.chartsContainerId = 'chartsContainer';
    this.emptyStateMessage = 'No metrics available.';

    // Window event handlers (stored for cleanup)
    this.resizeHandler = null;
    this.fullWidthChangedHandler = null;
    this.resizeTimeout = null;
  }

  /**
   * Initialize common DOM elements.
   * Subclasses can override and call super.initializeElements() first.
   */
  initializeElements() {
    this.chartsContainer = document.getElementById(this.chartsContainerId);
    this.chartControls = document.getElementById('chartControls');
    this.sizeSBtn = document.getElementById('sizeS');
    this.sizeMBtn = document.getElementById('sizeM');
    this.sizeLBtn = document.getElementById('sizeL');
  }

  /**
   * Common initialization sequence.
   * Call this after setting chartsContainerId and other properties.
   */
  init() {
    this.initializeElements();
    this.initSizeControls();
    this.initResizeHandlers();
  }

  /**
   * Initialize size button click handlers.
   */
  initSizeControls() {
    if (this.sizeSBtn) {
      this.sizeSBtn.addEventListener('click', () => this.setChartSize('S'));
    }
    if (this.sizeMBtn) {
      this.sizeMBtn.addEventListener('click', () => this.setChartSize('M'));
    }
    if (this.sizeLBtn) {
      this.sizeLBtn.addEventListener('click', () => this.setChartSize('L'));
    }
    this.updateSizeButtons();
  }

  /**
   * Initialize window resize and fullWidthChanged event handlers.
   * Call this after initializeElements() in subclass constructor.
   */
  initResizeHandlers() {
    // Store handlers for cleanup
    this.resizeHandler = () => {
      clearTimeout(this.resizeTimeout);
      this.resizeTimeout = setTimeout(() => {
        this.applyAutoLayout();
      }, 150);
    };
    window.addEventListener('resize', this.resizeHandler);

    this.fullWidthChangedHandler = () => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          this.applyAutoLayout();
        });
      });
    };
    window.addEventListener('fullWidthChanged', this.fullWidthChangedHandler);
  }

  /**
   * Calculate chart dimensions based on container width and current size setting.
   *
   * @returns {{ columns: number, chartWidth: number, chartHeight: number, gap: number }}
   */
  calculateChartDimensions() {
    if (!this.chartsContainer) {
      return { columns: 1, chartWidth: 400, chartHeight: 225, gap: 32 };
    }

    const containerWidth = this.chartsContainer.clientWidth;
    return calculateChartDimensions(containerWidth, this.chartSize);
  }

  /**
   * Apply grid layout to charts container and update chart sizes.
   */
  applyAutoLayout() {
    if (!this.chartsContainer) return;

    const { columns, chartHeight, gap } = this.calculateChartDimensions();

    applyGridLayout(this.chartsContainer, columns, gap);
    updateChartHeights(this.chartsContainer, chartHeight);
    updateContainerPadding(this.chartsContainer, this.chartSize);

    requestAnimationFrame(() => {
      for (const chart of this.charts.values()) {
        if (chart.updateSize) {
          chart.updateSize();
        }
      }
    });
  }

  /**
   * Set chart size and persist to localStorage.
   *
   * @param {string} size - Chart size ('S', 'M', or 'L')
   */
  setChartSize(size) {
    this.chartSize = size;
    localStorage.setItem(CHART_SIZE_KEY, size);
    this.updateSizeButtons();
    this.applyAutoLayout();
  }

  /**
   * Update size button visual states based on current chart size.
   */
  updateSizeButtons() {
    const buttons = {
      S: this.sizeSBtn,
      M: this.sizeMBtn,
      L: this.sizeLBtn,
    };
    updateSizeButtonStyles(buttons, this.chartSize);
  }

  /**
   * Show chart controls (size buttons, etc).
   */
  showChartControls() {
    if (this.chartControls) {
      this.chartControls.classList.remove('hidden');
    }
  }

  /**
   * Hide chart controls.
   */
  hideChartControls() {
    if (this.chartControls) {
      this.chartControls.classList.add('hidden');
    }
  }

  /**
   * Create a metric chart with container and error handling.
   * Uses Template Method pattern - subclasses implement initializeChart().
   *
   * @param {string} metricName - Name of the metric
   * @param {object} metricData - Metric data (format depends on subclass)
   */
  createMetricChart(metricName, metricData) {
    const { chartHeight } = this.calculateChartDimensions();
    const { container, chartId } = createMetricChartContainer(metricName, chartHeight, this.chartSize);
    this.chartsContainer.appendChild(container);

    try {
      const chart = this.initializeChart(chartId, metricName, metricData, container);
      if (chart) {
        this.charts.set(metricName, chart);
      }
    } catch (error) {
      console.error(`Error creating chart for ${metricName}:`, error);
      container.innerHTML = '';
      const errorDisplay = createChartErrorDisplay(metricName, error.message);
      container.appendChild(errorDisplay);
    }
  }

  /**
   * Template method for chart initialization.
   * Subclasses must override this to create their specific chart type.
   *
   * @param {string} chartId - DOM ID for the chart element
   * @param {string} metricName - Name of the metric
   * @param {object} metricData - Metric data
   * @param {HTMLElement} container - Container element for the chart
   * @returns {object|null} - Chart instance or null if no data
   */
  initializeChart(chartId, metricName, metricData, container) {
    throw new Error('Subclasses must implement initializeChart()');
  }

  /**
   * Clear charts container and render charts for the given metrics data.
   * Common logic for clearing and iterating over metrics.
   *
   * @param {object} metricsData - Object mapping metric names to data
   * @returns {boolean} - True if charts were rendered, false if no data
   */
  clearAndRenderCharts(metricsData) {
    this.chartsContainer.innerHTML = '';
    this.charts.clear();

    if (!metricsData || Object.keys(metricsData).length === 0) {
      return false;
    }

    this.showChartControls();

    // Temporarily show container to get accurate width for layout calculation
    const wasHidden = this.chartsContainer.classList.contains('hidden');
    if (wasHidden) {
      this.chartsContainer.classList.remove('hidden');
    }

    this.applyAutoLayout();

    for (const [metricName, data] of Object.entries(metricsData)) {
      this.createMetricChart(metricName, data);
    }

    // Restore hidden state if it was hidden (caller will show it when ready)
    if (wasHidden) {
      this.chartsContainer.classList.add('hidden');
    }

    return true;
  }

  /**
   * Render metrics data. Shows empty state if no data available.
   *
   * @param {object} metricsData - Object mapping metric names to data
   */
  renderMetrics(metricsData) {
    if (!this.clearAndRenderCharts(metricsData)) {
      this.chartsContainer.innerHTML = `
        <div class="text-neutral-500 p-4 text-center">
          <p>${this.emptyStateMessage}</p>
        </div>
      `;
      this.hideChartControls();
    }
  }

  /**
   * Show error message in the charts container.
   *
   * @param {string} message - Error message to display
   */
  showError(message) {
    this.chartsContainer.innerHTML = `
      <div class="text-red-500 p-4">
        <p>An error occurred: ${escapeHtml(message)}</p>
      </div>
    `;
    this.hideChartControls();
  }

  /**
   * Clean up event listeners and resources.
   */
  destroy() {
    if (this.resizeHandler) {
      window.removeEventListener('resize', this.resizeHandler);
      this.resizeHandler = null;
    }
    if (this.fullWidthChangedHandler) {
      window.removeEventListener('fullWidthChanged', this.fullWidthChangedHandler);
      this.fullWidthChangedHandler = null;
    }
    if (this.resizeTimeout) {
      clearTimeout(this.resizeTimeout);
      this.resizeTimeout = null;
    }
    this.charts.clear();
  }
}
