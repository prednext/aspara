import { binarySearchByStep, calculateDataRanges, findNearestStepBinary } from './interaction-utils.js';

export class ChartInteraction {
  constructor(chart, renderer) {
    this.chart = chart;
    this.renderer = renderer;
    // 2.4 Optimization: Cache data ranges to avoid recalculation on every mouse move
    this._cachedRanges = null;
    this._lastDataRef = null;

    // Canvas event handlers (stored for cleanup)
    this.mousemoveHandler = null;
    this.mouseleaveHandler = null;
    this.mousedownHandler = null;
    this.mouseupHandler = null;
    this.dblclickHandler = null;
    this.contextmenuHandler = null;

    // Throttling for mousemove draw calls
    this._pendingMouseMoveDraw = false;
  }

  /**
   * Invalidate the cached data ranges. Call this when data changes.
   */
  invalidateRangesCache() {
    this._cachedRanges = null;
    this._lastDataRef = null;
  }

  /**
   * Get data ranges, using cache if data hasn't changed.
   * @returns {Object|null} Object with xMin, xMax, yMin, yMax or null
   */
  _getDataRanges() {
    // Check if data reference changed (simple identity check)
    if (this.chart.data?.series !== this._lastDataRef) {
      this._lastDataRef = this.chart.data?.series;
      this._cachedRanges = calculateDataRanges(this.chart.data?.series || []);
    }
    return this._cachedRanges;
  }

  setupEventListeners() {
    // Remove any existing listeners first to prevent duplicates
    this.removeEventListeners();

    // Store handlers for cleanup
    this.mousemoveHandler = (e) => this.handleMouseMove(e);
    this.mouseleaveHandler = () => this.handleMouseLeave();
    this.mousedownHandler = (e) => this.handleMouseDown(e);
    this.mouseupHandler = (e) => this.handleMouseUp(e);
    this.dblclickHandler = () => this.chart.resetZoom();
    this.contextmenuHandler = (e) => e.preventDefault();

    this.chart.canvas.addEventListener('mousemove', this.mousemoveHandler);
    this.chart.canvas.addEventListener('mouseleave', this.mouseleaveHandler);
    this.chart.canvas.addEventListener('mousedown', this.mousedownHandler);
    this.chart.canvas.addEventListener('mouseup', this.mouseupHandler);
    this.chart.canvas.addEventListener('dblclick', this.dblclickHandler);
    this.chart.canvas.addEventListener('contextmenu', this.contextmenuHandler);
  }

  /**
   * Remove event listeners from canvas.
   */
  removeEventListeners() {
    if (this.chart.canvas) {
      if (this.mousemoveHandler) {
        this.chart.canvas.removeEventListener('mousemove', this.mousemoveHandler);
      }
      if (this.mouseleaveHandler) {
        this.chart.canvas.removeEventListener('mouseleave', this.mouseleaveHandler);
      }
      if (this.mousedownHandler) {
        this.chart.canvas.removeEventListener('mousedown', this.mousedownHandler);
      }
      if (this.mouseupHandler) {
        this.chart.canvas.removeEventListener('mouseup', this.mouseupHandler);
      }
      if (this.dblclickHandler) {
        this.chart.canvas.removeEventListener('dblclick', this.dblclickHandler);
      }
      if (this.contextmenuHandler) {
        this.chart.canvas.removeEventListener('contextmenu', this.contextmenuHandler);
      }
    }
    this.mousemoveHandler = null;
    this.mouseleaveHandler = null;
    this.mousedownHandler = null;
    this.mouseupHandler = null;
    this.dblclickHandler = null;
    this.contextmenuHandler = null;
  }

  handleMouseMove(event) {
    const rect = this.chart.canvas.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;

    // Cache zoomState reference to avoid repeated property access
    const zoomState = this.chart.zoomState;

    if (zoomState.active) {
      zoomState.currentX = mouseX;
      zoomState.currentY = mouseY;
      // Throttle draw calls during zoom selection using requestAnimationFrame
      this._scheduleMouseMoveDraw();
      return;
    }

    if (!this.chart.data || !this.chart.data.series || this.chart.data.series.length === 0) {
      return;
    }

    const nearestPoint = this.findNearestPoint(mouseX, mouseY);

    if (nearestPoint) {
      this.chart.hoverPoint = nearestPoint;
      this._scheduleMouseMoveDraw();
    } else if (this.chart.hoverPoint) {
      this.chart.hoverPoint = null;
      this._scheduleMouseMoveDraw();
    }
  }

  /**
   * Schedule a draw call using requestAnimationFrame to throttle mousemove updates.
   */
  _scheduleMouseMoveDraw() {
    if (this._pendingMouseMoveDraw) {
      return;
    }
    this._pendingMouseMoveDraw = true;
    requestAnimationFrame(() => {
      this._pendingMouseMoveDraw = false;
      this.chart.draw();
    });
  }

  handleMouseLeave() {
    if (this.chart.hoverPoint) {
      this.chart.hoverPoint = null;
      this.chart.draw();
    }
  }

  handleMouseDown(event) {
    if (event.button !== 0) return;

    const rect = this.chart.canvas.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;

    const margin = this.chart.constructor.MARGIN;
    const plotWidth = this.chart.width - margin * 2;
    const plotHeight = this.chart.height - margin * 2;

    if (mouseX >= margin && mouseX <= margin + plotWidth && mouseY >= margin && mouseY <= margin + plotHeight) {
      this.chart.zoomState.active = true;
      this.chart.zoomState.startX = mouseX;
      this.chart.zoomState.startY = mouseY;
      this.chart.zoomState.currentX = mouseX;
      this.chart.zoomState.currentY = mouseY;
    }
  }

  handleMouseUp(event) {
    if (!this.chart.zoomState.active) return;

    this.chart.zoomState.active = false;

    const dragDistance =
      Math.abs(this.chart.zoomState.currentX - this.chart.zoomState.startX) + Math.abs(this.chart.zoomState.currentY - this.chart.zoomState.startY);

    if (dragDistance < this.chart.constructor.MIN_DRAG_DISTANCE) {
      this.chart.draw();
      return;
    }

    this.applyZoom();
  }

  findNearestPoint(mouseX, mouseY) {
    if (!this.chart.data || !this.chart.data.series || this.chart.data.series.length === 0) {
      return null;
    }

    const margin = this.chart.constructor.MARGIN;
    const plotWidth = this.chart.width - margin * 2;
    const plotHeight = this.chart.height - margin * 2;

    if (mouseX < margin || mouseX > margin + plotWidth || mouseY < margin || mouseY > margin + plotHeight) {
      return null;
    }

    // 2.4 Optimization: Use cached data ranges instead of recalculating on every mouse move
    const ranges = this._getDataRanges();
    if (!ranges) return null;

    let { xMin, xMax, yMin, yMax } = ranges;

    // Apply zoom if active
    if (this.chart.zoom.x) {
      xMin = this.chart.zoom.x.min;
      xMax = this.chart.zoom.x.max;
    }
    if (this.chart.zoom.y) {
      yMin = this.chart.zoom.y.min;
      yMax = this.chart.zoom.y.max;
    }

    const yRange = yMax - yMin;
    const yMinPadded = yMin - yRange * this.chart.constructor.Y_PADDING_RATIO;
    const yMaxPadded = yMax + yRange * this.chart.constructor.Y_PADDING_RATIO;

    // Use binary search to find nearest step - O(log M) instead of O(N×M)
    const nearestStep = findNearestStepBinary(mouseX, this.chart.data.series, margin, plotWidth, xMin, xMax);

    if (nearestStep === null) return null;

    // Collect points at the nearest step using binary search - O(N × log M)
    const nearestPoints = [];
    for (const series of this.chart.data.series) {
      if (!series.data?.steps?.length) continue;
      const { steps, values } = series.data;

      const style = this.chart.colorPalette.getRunStyle(series.name);

      // Use binary search instead of linear .find() - O(log M) instead of O(M)
      const result = binarySearchByStep(steps, values, nearestStep);

      if (result) {
        const x = margin + ((result.step - xMin) / (xMax - xMin)) * plotWidth;
        const y = margin + plotHeight - ((result.value - yMinPadded) / (yMaxPadded - yMinPadded)) * plotHeight;

        nearestPoints.push({
          data: { step: result.step, value: result.value },
          x: x,
          y: y,
          series: series.name,
          color: style.borderColor,
        });
      }
    }

    return nearestPoints.length > 0
      ? {
          points: nearestPoints,
          step: nearestStep,
        }
      : null;
  }

  drawHoverEffects() {
    if (!this.chart.hoverPoint || !this.chart.hoverPoint.points) return;

    for (const point of this.chart.hoverPoint.points) {
      this.chart.ctx.fillStyle = point.color;
      this.chart.ctx.strokeStyle = 'white';
      this.chart.ctx.lineWidth = 2;

      this.chart.ctx.beginPath();
      this.chart.ctx.arc(point.x, point.y, 5, 0, 2 * Math.PI);
      this.chart.ctx.fill();
      this.chart.ctx.stroke();
    }

    this.drawTooltip();
  }

  drawTooltip() {
    if (!this.chart.hoverPoint || !this.chart.hoverPoint.points) return;

    const firstPoint = this.chart.hoverPoint.points[0];
    let tooltipX = firstPoint.x + 10;
    let tooltipY = firstPoint.y - 10;

    const lineIndicatorLength = 16;
    const lineIndicatorGap = 6;
    const indicatorOffset = lineIndicatorLength + lineIndicatorGap;

    this.chart.ctx.font = '12px Arial';

    const headerText = `Step: ${this.chart.hoverPoint.step}`;
    let maxWidth = this.chart.ctx.measureText(headerText).width;

    for (const point of this.chart.hoverPoint.points) {
      const seriesText = `${point.series}: ${point.data.value.toFixed(3)}`;
      const textWidth = this.chart.ctx.measureText(seriesText).width;
      maxWidth = Math.max(maxWidth, textWidth + indicatorOffset);
    }

    const seriesLineHeight = 20;
    const headerLineHeight = 18;
    const paddingX = 12;
    const paddingY = 10;
    const tooltipWidth = maxWidth + paddingX * 2;
    const tooltipHeight = paddingY + headerLineHeight + 8 + this.chart.hoverPoint.points.length * seriesLineHeight + paddingY;

    if (tooltipX + tooltipWidth > this.chart.width) {
      tooltipX = firstPoint.x - tooltipWidth - 10;
    }
    if (tooltipY - tooltipHeight < 0) {
      tooltipY = firstPoint.y + 20;
    }

    this.renderer.drawRoundedRect(tooltipX, tooltipY - tooltipHeight, tooltipWidth, tooltipHeight, 6);
    this.chart.ctx.fillStyle = 'rgba(75, 85, 99, 0.95)';
    this.chart.ctx.fill();

    this.renderer.drawRoundedRect(tooltipX, tooltipY - tooltipHeight, tooltipWidth, tooltipHeight, 6);
    this.chart.ctx.strokeStyle = 'rgba(229, 231, 235, 0.3)';
    this.chart.ctx.lineWidth = 1;
    this.chart.ctx.stroke();

    this.chart.ctx.fillStyle = 'white';
    this.chart.ctx.textAlign = 'left';
    this.chart.ctx.textBaseline = 'middle';
    const headerY = tooltipY - tooltipHeight + paddingY + headerLineHeight / 2;
    this.chart.ctx.fillText(headerText, tooltipX + paddingX, headerY);

    for (let index = 0; index < this.chart.hoverPoint.points.length; index++) {
      const point = this.chart.hoverPoint.points[index];
      const lineY = tooltipY - tooltipHeight + paddingY + headerLineHeight + 8 + (index + 0.5) * seriesLineHeight;
      const indicatorY = lineY;

      const style = this.chart.colorPalette.getRunStyle(point.series);

      this.chart.ctx.strokeStyle = point.color;
      this.chart.ctx.lineWidth = 2;
      if (style.borderDash && style.borderDash.length > 0) {
        this.chart.ctx.setLineDash(style.borderDash);
      } else {
        this.chart.ctx.setLineDash([]);
      }
      this.chart.ctx.beginPath();
      this.chart.ctx.moveTo(tooltipX + paddingX, indicatorY);
      this.chart.ctx.lineTo(tooltipX + paddingX + lineIndicatorLength, indicatorY);
      this.chart.ctx.stroke();
      this.chart.ctx.setLineDash([]);

      this.chart.ctx.fillStyle = 'white';
      const seriesText = `${point.series}: ${point.data.value.toFixed(3)}`;
      this.chart.ctx.fillText(seriesText, tooltipX + paddingX + indicatorOffset, lineY);
    }
  }

  applyZoom() {
    if (!this.chart.data || !this.chart.data.series || this.chart.data.series.length === 0) return;

    // Use cached data ranges instead of recalculating
    const ranges = this._getDataRanges();
    if (!ranges) return;

    const { xMin: dataXMin, xMax: dataXMax, yMin: dataYMin, yMax: dataYMax } = ranges;

    const margin = 60;
    const plotWidth = this.chart.width - margin * 2;
    const plotHeight = this.chart.height - margin * 2;

    const zoomXMin = Math.min(this.chart.zoomState.startX, this.chart.zoomState.currentX);
    const zoomXMax = Math.max(this.chart.zoomState.startX, this.chart.zoomState.currentX);

    const xMinRatio = (zoomXMin - margin) / plotWidth;
    const xMaxRatio = (zoomXMax - margin) / plotWidth;

    const currentXMin = this.chart.zoom.x ? this.chart.zoom.x.min : dataXMin;
    const currentXMax = this.chart.zoom.x ? this.chart.zoom.x.max : dataXMax;
    const currentXRange = currentXMax - currentXMin;

    const newXMin = currentXMin + xMinRatio * currentXRange;
    const newXMax = currentXMin + xMaxRatio * currentXRange;

    const zoomYMin = Math.min(this.chart.zoomState.startY, this.chart.zoomState.currentY);
    const zoomYMax = Math.max(this.chart.zoomState.startY, this.chart.zoomState.currentY);

    const yMinRatio = (plotHeight - (zoomYMax - margin)) / plotHeight;
    const yMaxRatio = (plotHeight - (zoomYMin - margin)) / plotHeight;

    const currentYMin = this.chart.zoom.y ? this.chart.zoom.y.min : dataYMin;
    const currentYMax = this.chart.zoom.y ? this.chart.zoom.y.max : dataYMax;
    const currentYRange = currentYMax - currentYMin;

    const newYMin = currentYMin + yMinRatio * currentYRange;
    const newYMax = currentYMin + yMaxRatio * currentYRange;

    this.chart.zoom.x = { min: newXMin, max: newXMax };
    this.chart.zoom.y = { min: newYMin, max: newYMax };

    if (this.chart.onZoomChange) {
      this.chart.onZoomChange({ x: this.chart.zoom.x, y: this.chart.zoom.y });
    }

    this.chart.draw();
  }

  drawZoomSelection() {
    if (!this.chart.zoomState.active) return;

    const startX = this.chart.zoomState.startX;
    const startY = this.chart.zoomState.startY;
    const currentX = this.chart.zoomState.currentX;
    const currentY = this.chart.zoomState.currentY;

    const x = Math.min(startX, currentX);
    const y = Math.min(startY, currentY);
    const width = Math.abs(currentX - startX);
    const height = Math.abs(currentY - startY);

    this.chart.ctx.fillStyle = 'rgba(0, 123, 255, 0.1)';
    this.chart.ctx.fillRect(x, y, width, height);

    this.chart.ctx.strokeStyle = 'rgba(0, 123, 255, 0.5)';
    this.chart.ctx.lineWidth = 1;
    this.chart.ctx.setLineDash([4, 4]);
    this.chart.ctx.strokeRect(x, y, width, height);

    this.chart.ctx.setLineDash([]);
  }
}
