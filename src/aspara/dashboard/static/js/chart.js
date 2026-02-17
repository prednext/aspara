/**
 * Canvas-based chart component for metrics visualization.
 * Supports multiple series, zoom, hover tooltips, and data export.
 */
import { ChartColorPalette } from './chart/color-palette.js';
import { ChartControls } from './chart/controls.js';
import { ChartExport } from './chart/export.js';
import { ChartInteraction } from './chart/interaction.js';
import { ChartRenderer } from './chart/renderer.js';

export class Chart {
  // Chart layout constants
  static MARGIN = 60;
  static CANVAS_SCALE_FACTOR = 1.5; // Reduced from 2.5 for better performance
  static SIZE_UPDATE_RETRY_DELAY_MS = 100;
  static FULLSCREEN_UPDATE_DELAY_MS = 100;
  static MIN_DRAG_DISTANCE = 10;

  // Grid constants
  static X_GRID_COUNT = 10;
  static Y_GRID_COUNT = 8;
  static Y_PADDING_RATIO = 0.1;

  // Style constants
  static LINE_WIDTH = 1.5; // Normal view
  static LINE_WIDTH_FULLSCREEN = 2.5; // Fullscreen view
  static GRID_LINE_WIDTH = 0.5;
  static LEGEND_ITEM_SPACING = 16;
  static LEGEND_LINE_LENGTH = 16;
  static LEGEND_TEXT_OFFSET = 4;
  static LEGEND_Y_OFFSET = 30;

  // Animation constants
  static ANIMATION_PULSE_DURATION_MS = 1000;

  constructor(containerId, options = {}) {
    this.container = document.querySelector(containerId);
    if (!this.container) {
      throw new Error(`Container ${containerId} not found`);
    }

    this.data = null;
    this.width = 0;
    this.height = 0;
    this.onZoomChange = options.onZoomChange || null;

    // Color palette for managing series styles
    this.colorPalette = new ChartColorPalette();

    // Initialize modules
    this.renderer = new ChartRenderer(this);
    this.chartExport = new ChartExport(this);
    this.interaction = new ChartInteraction(this, this.renderer);
    this.controls = new ChartControls(this, this.chartExport);

    this.hoverPoint = null;

    this.zoomState = {
      active: false,
      startX: null,
      startY: null,
      currentX: null,
      currentY: null,
    };
    this.zoom = { x: null, y: null };

    // Fullscreen event handler (stored for cleanup)
    this.fullscreenChangeHandler = null;

    // Data range cache for performance optimization
    this._cachedDataRanges = null;
    this._lastDataRef = null;

    this.init();
  }

  init() {
    this.container.innerHTML = '';

    this.canvas = document.createElement('canvas');
    this.canvas.style.border = '1px solid #e5e7eb';
    this.canvas.style.display = 'block';
    this.canvas.style.maxWidth = '100%';

    this.container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');

    this.ctx.imageSmoothingEnabled = true;
    this.ctx.imageSmoothingQuality = 'high';

    // For throttling draw calls
    this.pendingDraw = false;

    this.updateSize();
    this.interaction.setupEventListeners();
    this.setupFullscreenListener();
    this.controls.create();
  }

  updateSize() {
    // Use clientWidth/clientHeight to get size excluding border
    const rect = this.container.getBoundingClientRect?.();
    const width = this.container.clientWidth || rect?.width || 0;
    const height = this.container.clientHeight || rect?.height || 0;

    // Retry later if container is not yet visible
    if (width === 0 || height === 0) {
      // Avoid infinite retry loops - only retry if we haven't set a size yet
      if (this.width === 0 && this.height === 0) {
        setTimeout(() => this.updateSize(), Chart.SIZE_UPDATE_RETRY_DELAY_MS);
      }
      return;
    }

    this.width = width;
    this.height = height;

    this.ctx.setTransform(1, 0, 0, 1, 0, 0);

    const dpr = window.devicePixelRatio || 1;
    const totalScale = dpr * Chart.CANVAS_SCALE_FACTOR;

    // Set internal canvas resolution (high-DPI)
    this.canvas.width = this.width * totalScale;
    this.canvas.height = this.height * totalScale;

    // Set CSS display size to exact pixel values (matching internal aspect ratio)
    this.canvas.style.width = `${this.width}px`;
    this.canvas.style.height = `${this.height}px`;
    this.canvas.style.display = 'block';

    this.ctx.scale(totalScale, totalScale);

    // Redraw if data is already set
    if (this.data) {
      this.draw();
    }
  }

  setData(data) {
    this.data = data;
    // Invalidate data range cache when data changes
    this._cachedDataRanges = null;
    this._lastDataRef = null;
    if (data?.series) {
      this.colorPalette.ensureRunStyles(data.series.map((s) => s.name));
    }
    this.draw();
  }

  /**
   * Get cached data ranges, recalculating only when data changes.
   * @returns {Object|null} Object with xMin, xMax, yMin, yMax or null
   */
  _getDataRanges() {
    // Check if data reference changed
    if (this.data?.series !== this._lastDataRef) {
      this._lastDataRef = this.data?.series;
      this._cachedDataRanges = this._calculateDataRanges();
    }
    return this._cachedDataRanges;
  }

  /**
   * Calculate data ranges from all series.
   * @returns {Object|null} Object with xMin, xMax, yMin, yMax or null
   */
  _calculateDataRanges() {
    if (!this.data?.series?.length) return null;

    let xMin = Number.POSITIVE_INFINITY;
    let xMax = Number.NEGATIVE_INFINITY;
    let yMin = Number.POSITIVE_INFINITY;
    let yMax = Number.NEGATIVE_INFINITY;

    for (const series of this.data.series) {
      if (!series.data?.steps?.length) continue;
      const { steps, values } = series.data;

      // steps are sorted, so O(1) for min/max
      xMin = Math.min(xMin, steps[0]);
      xMax = Math.max(xMax, steps[steps.length - 1]);

      // values min/max
      for (let i = 0; i < values.length; i++) {
        if (values[i] < yMin) yMin = values[i];
        if (values[i] > yMax) yMax = values[i];
      }
    }

    if (xMin === Number.POSITIVE_INFINITY) return null;

    return { xMin, xMax, yMin, yMax };
  }

  draw() {
    // Skip drawing if canvas size is not yet initialized
    if (this.width === 0 || this.height === 0) {
      return;
    }

    this.ctx.fillStyle = 'white';
    this.ctx.fillRect(0, 0, this.width, this.height);

    if (!this.data) {
      console.warn('Chart.draw(): No data set');
      return;
    }

    if (!this.data.series || !Array.isArray(this.data.series)) {
      console.error('Chart.draw(): Invalid data format - series must be an array');
      return;
    }

    if (this.data.series.length === 0) {
      console.warn('Chart.draw(): Empty series array');
      return;
    }

    const margin = Chart.MARGIN;
    const plotWidth = this.width - margin * 2;
    const plotHeight = this.height - margin * 2;

    // Use cached data ranges for performance
    const ranges = this._getDataRanges();
    if (!ranges) {
      console.warn('Chart.draw(): No valid data points in series');
      return;
    }

    let { xMin, xMax, yMin, yMax } = ranges;

    if (this.zoom.x) {
      xMin = this.zoom.x.min;
      xMax = this.zoom.x.max;
    }
    if (this.zoom.y) {
      yMin = this.zoom.y.min;
      yMax = this.zoom.y.max;
    }

    const yRange = yMax - yMin;
    const yMinPadded = yMin - yRange * Chart.Y_PADDING_RATIO;
    const yMaxPadded = yMax + yRange * Chart.Y_PADDING_RATIO;

    this.renderer.drawGrid(margin, plotWidth, plotHeight, xMin, xMax, yMinPadded, yMaxPadded);
    this.renderer.drawAxisLabels(margin, plotWidth, plotHeight, xMin, xMax, yMinPadded, yMaxPadded);

    // Clip to plot area
    this.ctx.save();
    this.ctx.beginPath();
    this.ctx.rect(margin, margin, plotWidth, plotHeight);
    this.ctx.clip();

    for (const series of this.data.series) {
      if (!series.data?.steps?.length) continue;
      const { steps, values } = series.data;

      const style = this.colorPalette.getRunStyle(series.name);

      this.ctx.strokeStyle = style.borderColor;
      this.ctx.lineWidth = this.getLineWidth();
      this.ctx.lineCap = 'round';
      this.ctx.lineJoin = 'round';

      // Apply border dash pattern
      if (style.borderDash && style.borderDash.length > 0) {
        this.ctx.setLineDash(style.borderDash);
      } else {
        this.ctx.setLineDash([]);
      }

      this.ctx.beginPath();

      for (let i = 0; i < steps.length; i++) {
        const x = margin + ((steps[i] - xMin) / (xMax - xMin)) * plotWidth;
        const y = margin + plotHeight - ((values[i] - yMinPadded) / (yMaxPadded - yMinPadded)) * plotHeight;

        if (i === 0) {
          this.ctx.moveTo(x, y);
        } else {
          this.ctx.lineTo(x, y);
        }
      }

      this.ctx.stroke();
      this.ctx.setLineDash([]); // Reset dash pattern
    }

    this.ctx.restore();
    this.renderer.drawLegend();
    this.interaction.drawHoverEffects();
    this.interaction.drawZoomSelection();
  }

  getLineWidth() {
    if (document.fullscreenElement === this.container) {
      return Chart.LINE_WIDTH_FULLSCREEN;
    }
    return Chart.LINE_WIDTH;
  }

  getRunStyle(seriesName) {
    return this.colorPalette.getRunStyle(seriesName);
  }

  setupFullscreenListener() {
    // Store handler for cleanup
    this.fullscreenChangeHandler = () => {
      setTimeout(() => {
        this.updateSize();
      }, Chart.FULLSCREEN_UPDATE_DELAY_MS);
    };
    document.addEventListener('fullscreenchange', this.fullscreenChangeHandler);
  }

  resetZoom() {
    this.zoom.x = null;
    this.zoom.y = null;
    this.draw();
  }

  setExternalZoom(zoomState) {
    if (zoomState?.x) {
      this.zoom.x = { ...zoomState.x };
      this.draw();
    }
  }

  /**
   * Add a new data point to an existing series (SoA format)
   * @param {string} runName - Name of the run
   * @param {number} step - Step number
   * @param {number} value - Metric value
   */
  addDataPoint(runName, step, value) {
    console.log(`[Chart] addDataPoint called: run=${runName}, step=${step}, value=${value}`);

    if (!this.data || !this.data.series) {
      console.warn('[Chart] No data or series available');
      return;
    }

    // Find the series for this run
    let series = this.data.series.find((s) => s.name === runName);

    if (!series) {
      // Create new series if it doesn't exist (SoA format)
      series = {
        name: runName,
        data: { steps: [], values: [] },
      };
      this.data.series.push(series);
    }

    const { steps, values } = series.data;

    // Binary search to find insertion position
    let left = 0;
    let right = steps.length;
    while (left < right) {
      const mid = (left + right) >> 1;
      if (steps[mid] < step) {
        left = mid + 1;
      } else if (steps[mid] > step) {
        right = mid;
      } else {
        // Exact match - update existing value
        values[mid] = value;
        this.scheduleDraw();
        return;
      }
    }

    // Insert at the found position (usually at the end, so O(1) in practice)
    steps.splice(left, 0, step);
    values.splice(left, 0, value);

    // Invalidate data range cache when data changes
    this._cachedDataRanges = null;

    // Schedule redraw using requestAnimationFrame to throttle updates
    this.scheduleDraw();
  }

  /**
   * Schedule a draw operation using requestAnimationFrame
   * This prevents excessive redraws when multiple data points arrive rapidly
   */
  scheduleDraw() {
    console.log('[Chart] scheduleDraw called, pendingDraw:', this.pendingDraw);

    if (this.pendingDraw) {
      return; // Draw already scheduled
    }

    this.pendingDraw = true;
    requestAnimationFrame(() => {
      console.log('[Chart] requestAnimationFrame callback executing');
      this.pendingDraw = false;
      this.draw();
    });
  }

  /**
   * Clean up event listeners and resources.
   */
  destroy() {
    if (this.fullscreenChangeHandler) {
      document.removeEventListener('fullscreenchange', this.fullscreenChangeHandler);
      this.fullscreenChangeHandler = null;
    }
    if (this.interaction) {
      this.interaction.removeEventListeners();
    }
    if (this.controls) {
      this.controls.destroy();
    }
  }
}
