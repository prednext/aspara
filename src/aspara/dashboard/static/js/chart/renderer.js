export class ChartRenderer {
  constructor(chart) {
    this.chart = chart;
  }

  drawGrid(margin, plotWidth, plotHeight, xMin, xMax, yMin, yMax) {
    this.chart.ctx.strokeStyle = '#e0e0e0';
    this.chart.ctx.lineWidth = this.chart.constructor.GRID_LINE_WIDTH;

    const xGridCount = this.chart.constructor.X_GRID_COUNT;
    for (let i = 0; i <= xGridCount; i++) {
      const x = margin + (i / xGridCount) * plotWidth;
      this.chart.ctx.beginPath();
      this.chart.ctx.moveTo(x, margin);
      this.chart.ctx.lineTo(x, margin + plotHeight);
      this.chart.ctx.stroke();
    }

    const yGridCount = this.chart.constructor.Y_GRID_COUNT;
    for (let i = 0; i <= yGridCount; i++) {
      const y = margin + (i / yGridCount) * plotHeight;
      this.chart.ctx.beginPath();
      this.chart.ctx.moveTo(margin, y);
      this.chart.ctx.lineTo(margin + plotWidth, y);
      this.chart.ctx.stroke();
    }
  }

  drawAxisLabels(margin, plotWidth, plotHeight, xMin, xMax, yMin, yMax) {
    this.chart.ctx.fillStyle = '#666';
    this.chart.ctx.font = '11px Arial';
    this.chart.ctx.textAlign = 'center';

    const xGridCount = this.chart.constructor.X_GRID_COUNT;
    for (let i = 0; i <= xGridCount; i++) {
      const value = xMin + (i / xGridCount) * (xMax - xMin);
      const x = margin + (i / xGridCount) * plotWidth;
      const y = margin + plotHeight + 15;

      if (i % 2 === 0) {
        let label;
        if (value >= 1000) {
          label = `${Math.round(value / 1000)}k`;
        } else {
          label = Math.round(value).toString();
        }

        this.chart.ctx.fillText(label, x, y);
      }
    }

    this.chart.ctx.textAlign = 'right';
    const yGridCount = this.chart.constructor.Y_GRID_COUNT;
    for (let i = 0; i <= yGridCount; i++) {
      const value = yMax - (i / yGridCount) * (yMax - yMin);
      const x = margin - 8;
      const y = margin + (i / yGridCount) * plotHeight + 4;

      if (i % 2 === 0) {
        let label;
        if (Math.abs(value) >= 1) {
          label = value.toFixed(1);
        } else {
          label = value.toFixed(3);
        }

        this.chart.ctx.fillText(label, x, y);
      }
    }
  }

  drawLegend() {
    if (!this.chart.data || !this.chart.data.series || this.chart.data.series.length <= 1) {
      return;
    }

    const itemSpacing = this.chart.constructor.LEGEND_ITEM_SPACING;
    const lineLength = this.chart.constructor.LEGEND_LINE_LENGTH;
    const textOffset = this.chart.constructor.LEGEND_TEXT_OFFSET;

    this.chart.ctx.font = '11px Arial';

    const items = this.chart.data.series.map((series) => {
      const style = this.chart.colorPalette.getRunStyle(series.name);
      const textWidth = this.chart.ctx.measureText(series.name).width;
      return {
        name: series.name,
        style: style,
        width: lineLength + textOffset + textWidth,
      };
    });

    const totalWidth = items.reduce((sum, item, i) => sum + item.width + (i < items.length - 1 ? itemSpacing : 0), 0);

    const legendY = this.chart.height - this.chart.constructor.LEGEND_Y_OFFSET;
    let currentX = (this.chart.width - totalWidth) / 2;

    // Cache context reference to avoid repeated property access in loop
    const ctx = this.chart.ctx;

    for (const item of items) {
      ctx.strokeStyle = item.style.borderColor;
      ctx.lineWidth = 2;
      if (item.style.borderDash && item.style.borderDash.length > 0) {
        ctx.setLineDash(item.style.borderDash);
      } else {
        ctx.setLineDash([]);
      }
      ctx.beginPath();
      ctx.moveTo(currentX, legendY);
      ctx.lineTo(currentX + lineLength, legendY);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = '#374151';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText(item.name, currentX + lineLength + textOffset, legendY);

      currentX += item.width + itemSpacing;
    }
  }

  drawRoundedRect(x, y, width, height, radius) {
    this.chart.ctx.beginPath();
    this.chart.ctx.moveTo(x + radius, y);
    this.chart.ctx.lineTo(x + width - radius, y);
    this.chart.ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    this.chart.ctx.lineTo(x + width, y + height - radius);
    this.chart.ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    this.chart.ctx.lineTo(x + radius, y + height);
    this.chart.ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    this.chart.ctx.lineTo(x, y + radius);
    this.chart.ctx.quadraticCurveTo(x, y, x + radius, y);
    this.chart.ctx.closePath();
  }
}
