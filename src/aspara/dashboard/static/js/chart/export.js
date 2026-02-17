import { buildExportFileName, calculateExportDimensions, generateCSVContent, getExportFileName } from './export-utils.js';

export class ChartExport {
  constructor(chart) {
    this.chart = chart;
  }

  downloadData(format) {
    if (!this.chart.data || !this.chart.data.series || this.chart.data.series.length === 0) {
      return;
    }

    switch (format) {
      case 'CSV':
        this.downloadCSV();
        break;
      case 'SVG':
        this.downloadSVG();
        break;
      case 'PNG':
        this.downloadPNG();
        break;
    }
  }

  downloadCSV() {
    const csvContent = generateCSVContent(this.chart.data.series);

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    const fileName = getExportFileName(this.chart.data);

    link.setAttribute('href', url);
    link.setAttribute('download', `${fileName}.csv`);
    link.style.display = 'none';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  downloadSVG() {
    const svgNamespace = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNamespace, 'svg');

    const { useZoomedArea, margin, plotWidth, plotHeight } = calculateExportDimensions(this.chart);

    if (useZoomedArea) {
      svg.setAttribute('width', plotWidth);
      svg.setAttribute('height', plotHeight);
      svg.setAttribute('viewBox', `0 0 ${plotWidth} ${plotHeight}`);

      const background = document.createElementNS(svgNamespace, 'rect');
      background.setAttribute('width', plotWidth);
      background.setAttribute('height', plotHeight);
      background.setAttribute('fill', 'white');
      svg.appendChild(background);

      const tempCanvas = document.createElement('canvas');
      tempCanvas.width = plotWidth;
      tempCanvas.height = plotHeight;
      const tempCtx = tempCanvas.getContext('2d');

      tempCtx.drawImage(this.chart.canvas, margin, margin, plotWidth, plotHeight, 0, 0, plotWidth, plotHeight);

      const canvasImage = document.createElementNS(svgNamespace, 'image');
      canvasImage.setAttribute('width', plotWidth);
      canvasImage.setAttribute('height', plotHeight);
      canvasImage.setAttribute('href', tempCanvas.toDataURL('image/png'));
      svg.appendChild(canvasImage);
    } else {
      svg.setAttribute('width', this.chart.width);
      svg.setAttribute('height', this.chart.height);
      svg.setAttribute('viewBox', `0 0 ${this.chart.width} ${this.chart.height}`);

      const background = document.createElementNS(svgNamespace, 'rect');
      background.setAttribute('width', this.chart.width);
      background.setAttribute('height', this.chart.height);
      background.setAttribute('fill', 'white');
      svg.appendChild(background);

      const canvasImage = document.createElementNS(svgNamespace, 'image');
      canvasImage.setAttribute('width', this.chart.width);
      canvasImage.setAttribute('height', this.chart.height);
      canvasImage.setAttribute('href', this.chart.canvas.toDataURL('image/png'));
      svg.appendChild(canvasImage);
    }

    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svg);

    const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    const fileName = buildExportFileName(getExportFileName(this.chart.data), useZoomedArea);

    link.setAttribute('href', url);
    link.setAttribute('download', `${fileName}.svg`);
    link.style.display = 'none';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  downloadPNG() {
    const { useZoomedArea, margin, plotWidth, plotHeight } = calculateExportDimensions(this.chart);

    let dataURL;

    if (useZoomedArea) {
      const tempCanvas = document.createElement('canvas');
      tempCanvas.width = plotWidth;
      tempCanvas.height = plotHeight;
      const tempCtx = tempCanvas.getContext('2d');

      tempCtx.drawImage(this.chart.canvas, margin, margin, plotWidth, plotHeight, 0, 0, plotWidth, plotHeight);

      dataURL = tempCanvas.toDataURL('image/png');
    } else {
      dataURL = this.chart.canvas.toDataURL('image/png');
    }

    const fileName = buildExportFileName(getExportFileName(this.chart.data), useZoomedArea);

    const link = document.createElement('a');
    link.setAttribute('href', dataURL);
    link.setAttribute('download', `${fileName}.png`);
    link.style.display = 'none';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
}
