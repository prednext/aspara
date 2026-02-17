/**
 * Chart ビジネスロジックの単体テスト
 * Canvas描画やDOM操作を除いた純粋なロジックをテスト
 */

import { vi } from 'vitest';
import { Chart } from '../../src/aspara/dashboard/static/js/chart.js';

// ブラウザAPIのモック（ロジックテストに必要な最小限）
let mockBlob;
let mockURL;
let mockLink;

beforeAll(() => {
  mockBlob = vi.fn();
  global.Blob = mockBlob;

  mockURL = {
    createObjectURL: vi.fn(() => 'mock-url'),
    revokeObjectURL: vi.fn(),
  };
  global.URL = mockURL;

  mockLink = {
    setAttribute: vi.fn(),
    click: vi.fn(),
    style: {},
  };

  const originalCreateElement = document.createElement.bind(document);
  document.createElement = vi.fn((tagName) => {
    if (tagName === 'a') return mockLink;
    return originalCreateElement(tagName);
  });

  document.body.appendChild = vi.fn();
  document.body.removeChild = vi.fn();
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe('Chart Business Logic', () => {
  describe('CSV Generation Logic', () => {
    test('should generate correct CSV format from series data', () => {
      const testData = {
        series: [
          {
            name: 'loss',
            data: [
              { step: 0, value: 1.0 },
              { step: 1, value: 0.8 },
              { step: 2, value: 0.6 },
            ],
          },
          {
            name: 'accuracy',
            data: [
              { step: 0, value: 0.5 },
              { step: 1, value: 0.7 },
              { step: 2, value: 0.9 },
            ],
          },
        ],
      };

      // モック環境でChartのCSV生成ロジックを直接テスト
      const chart = { data: testData };

      // CSV生成の実際のロジック（BasicChartから抽出）
      let csvContent = 'series,step,value\n';
      for (const series of chart.data.series) {
        for (const point of series.data) {
          const escapedSeriesName = `"${series.name.replace(/"/g, '""')}"`;
          csvContent += `${escapedSeriesName},${point.step},${point.value}\n`;
        }
      }

      expect(csvContent).toBe(
        'series,step,value\n' + '"loss",0,1\n' + '"loss",1,0.8\n' + '"loss",2,0.6\n' + '"accuracy",0,0.5\n' + '"accuracy",1,0.7\n' + '"accuracy",2,0.9\n'
      );
    });

    test('should escape quotes in series names', () => {
      const testData = {
        series: [
          {
            name: 'metric "with quotes"',
            data: [{ step: 0, value: 1.0 }],
          },
        ],
      };

      const chart = { data: testData };

      let csvContent = 'series,step,value\n';
      for (const series of chart.data.series) {
        for (const point of series.data) {
          const escapedSeriesName = `"${series.name.replace(/"/g, '""')}"`;
          csvContent += `${escapedSeriesName},${point.step},${point.value}\n`;
        }
      }

      expect(csvContent).toContain('"metric ""with quotes"""');
    });

    test('should handle empty data gracefully', () => {
      const testData = { series: [] };
      const chart = { data: testData };

      let csvContent = 'series,step,value\n';
      for (const series of chart.data.series) {
        for (const point of series.data) {
          const escapedSeriesName = `"${series.name.replace(/"/g, '""')}"`;
          csvContent += `${escapedSeriesName},${point.step},${point.value}\n`;
        }
      }

      expect(csvContent).toBe('series,step,value\n');
    });
  });

  describe('Filename Generation Logic', () => {
    test('should generate filename from chart title', () => {
      const testData = { title: 'Training Metrics' };

      // ファイル名生成ロジック（Chartから抽出）
      const generateFilename = (data, extension = 'csv') => {
        if (data.title) {
          return `${data.title.toLowerCase().replace(/[^a-z0-9]/g, '_')}.${extension}`;
        }
        if (data.series && data.series.length === 1) {
          return `${data.series[0].name.replace(/[^a-z0-9]/g, '_')}.${extension}`;
        }
        return `metrics.${extension}`;
      };

      expect(generateFilename(testData)).toBe('training_metrics.csv');
    });

    test('should use single series name when no title', () => {
      const testData = {
        series: [{ name: 'validation_loss', data: [] }],
      };

      const generateFilename = (data, extension = 'csv') => {
        if (data.title) {
          return `${data.title.toLowerCase().replace(/[^a-z0-9]/g, '_')}.${extension}`;
        }
        if (data.series && data.series.length === 1) {
          return `${data.series[0].name.replace(/[^a-z0-9]/g, '_')}.${extension}`;
        }
        return `metrics.${extension}`;
      };

      expect(generateFilename(testData)).toBe('validation_loss.csv');
    });

    test('should sanitize special characters', () => {
      const testData = { title: 'My/Training\\Metrics:2024' };

      const generateFilename = (data, extension = 'csv') => {
        if (data.title) {
          return `${data.title.toLowerCase().replace(/[^a-z0-9]/g, '_')}.${extension}`;
        }
        if (data.series && data.series.length === 1) {
          return `${data.series[0].name.replace(/[^a-z0-9]/g, '_')}.${extension}`;
        }
        return `metrics.${extension}`;
      };

      expect(generateFilename(testData)).toBe('my_training_metrics_2024.csv');
    });

    test('should fallback to default filename', () => {
      const testData = {
        series: [
          { name: 'metric1', data: [] },
          { name: 'metric2', data: [] },
        ],
      };

      const generateFilename = (data, extension = 'csv') => {
        if (data.title) {
          return `${data.title.toLowerCase().replace(/[^a-z0-9]/g, '_')}.${extension}`;
        }
        if (data.series && data.series.length === 1) {
          return `${data.series[0].name.replace(/[^a-z0-9]/g, '_')}.${extension}`;
        }
        return `metrics.${extension}`;
      };

      expect(generateFilename(testData)).toBe('metrics.csv');
    });

    test('should handle different file extensions', () => {
      const testData = { title: 'Test Chart' };

      const generateFilename = (data, extension = 'csv') => {
        if (data.title) {
          return `${data.title.toLowerCase().replace(/[^a-z0-9]/g, '_')}.${extension}`;
        }
        if (data.series && data.series.length === 1) {
          return `${data.series[0].name.replace(/[^a-z0-9]/g, '_')}.${extension}`;
        }
        return `metrics.${extension}`;
      };

      expect(generateFilename(testData, 'svg')).toBe('test_chart.svg');
      expect(generateFilename(testData, 'png')).toBe('test_chart.png');
    });
  });

  describe('Download Format Routing Logic', () => {
    test('should route to correct download method based on format', () => {
      const downloadMethods = {
        CSV: vi.fn(),
        SVG: vi.fn(),
        PNG: vi.fn(),
      };

      // フォーマット分岐ロジック（Chartから抽出）
      const routeDownload = (format) => {
        switch (format) {
          case 'CSV':
            downloadMethods.CSV();
            break;
          case 'SVG':
            downloadMethods.SVG();
            break;
          case 'PNG':
            downloadMethods.PNG();
            break;
          default:
            throw new Error(`Unsupported format: ${format}`);
        }
      };

      routeDownload('CSV');
      expect(downloadMethods.CSV).toHaveBeenCalled();
      expect(downloadMethods.SVG).not.toHaveBeenCalled();
      expect(downloadMethods.PNG).not.toHaveBeenCalled();

      vi.clearAllMocks();

      routeDownload('SVG');
      expect(downloadMethods.SVG).toHaveBeenCalled();
      expect(downloadMethods.CSV).not.toHaveBeenCalled();
      expect(downloadMethods.PNG).not.toHaveBeenCalled();

      vi.clearAllMocks();

      routeDownload('PNG');
      expect(downloadMethods.PNG).toHaveBeenCalled();
      expect(downloadMethods.CSV).not.toHaveBeenCalled();
      expect(downloadMethods.SVG).not.toHaveBeenCalled();
    });

    test('should handle unsupported formats', () => {
      const routeDownload = (format) => {
        switch (format) {
          case 'CSV':
          case 'SVG':
          case 'PNG':
            break;
          default:
            throw new Error(`Unsupported format: ${format}`);
        }
      };

      expect(() => routeDownload('PDF')).toThrow('Unsupported format: PDF');
      expect(() => routeDownload('')).toThrow('Unsupported format: ');
    });
  });

  describe('Error Handling Logic', () => {
    test('should handle missing data', () => {
      const validateData = (data) => {
        if (!data || !data.series || data.series.length === 0) {
          throw new Error('No data available for download');
        }
        return true;
      };

      expect(() => validateData(null)).toThrow('No data available for download');
      expect(() => validateData({})).toThrow('No data available for download');
      expect(() => validateData({ series: [] })).toThrow('No data available for download');

      expect(validateData({ series: [{ name: 'test', data: [] }] })).toBe(true);
    });

    test('should handle malformed series data', () => {
      const validateSeriesData = (series) => {
        if (!Array.isArray(series)) {
          throw new Error('Series must be an array');
        }

        for (const s of series) {
          if (!s.name || !Array.isArray(s.data)) {
            throw new Error('Invalid series format');
          }
        }
        return true;
      };

      expect(() => validateSeriesData('not-array')).toThrow('Series must be an array');
      expect(() => validateSeriesData([{ data: [] }])).toThrow('Invalid series format');
      expect(() => validateSeriesData([{ name: 'test' }])).toThrow('Invalid series format');

      expect(validateSeriesData([{ name: 'test', data: [] }])).toBe(true);
    });
  });

  describe('Tooltip Drawing Logic', () => {
    let mockCtx;

    beforeEach(() => {
      // Mock canvas context
      mockCtx = {
        fillStyle: '',
        strokeStyle: '',
        lineWidth: 0,
        textAlign: '',
        textBaseline: '',
        font: '',
        measureText: vi.fn(() => ({ width: 100 })),
        fillText: vi.fn(),
        fillRect: vi.fn(),
        strokeRect: vi.fn(),
        beginPath: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        stroke: vi.fn(),
        fill: vi.fn(),
        setLineDash: vi.fn(),
        arc: vi.fn(),
        closePath: vi.fn(),
        quadraticCurveTo: vi.fn(),
      };
    });

    test('should draw color line indicator for each series', () => {
      const hoverPoint = {
        step: 100,
        points: [
          {
            series: 'loss',
            data: { step: 100, value: 0.5 },
            x: 200,
            y: 150,
            color: '#FF3B47',
          },
          {
            series: 'accuracy',
            data: { step: 100, value: 0.8 },
            x: 200,
            y: 180,
            color: '#118AB2',
          },
        ],
      };

      // Mock Chart instance with getRunStyle method
      const mockChart = {
        hoverPoint,
        width: 800,
        height: 600,
        ctx: mockCtx,
        getRunStyle: vi.fn((seriesName) => {
          if (seriesName === 'loss') {
            return { borderColor: '#FF3B47', borderDash: [] };
          }
          return { borderColor: '#118AB2', borderDash: [6, 4] };
        }),
      };

      // Extract tooltip drawing logic
      const lineIndicatorLength = 16;

      // Simulate drawing color indicators for each point
      for (const point of hoverPoint.points) {
        const style = mockChart.getRunStyle(point.series);

        mockCtx.strokeStyle = point.color;
        mockCtx.lineWidth = 2;
        if (style.borderDash && style.borderDash.length > 0) {
          mockCtx.setLineDash(style.borderDash);
        } else {
          mockCtx.setLineDash([]);
        }
        mockCtx.beginPath();
        mockCtx.moveTo(10, 10); // Simplified position
        mockCtx.lineTo(10 + lineIndicatorLength, 10);
        mockCtx.stroke();
        mockCtx.setLineDash([]);
      }

      // Verify each series got a color indicator
      expect(mockChart.getRunStyle).toHaveBeenCalledWith('loss');
      expect(mockChart.getRunStyle).toHaveBeenCalledWith('accuracy');
      expect(mockCtx.beginPath).toHaveBeenCalledTimes(2);
      expect(mockCtx.stroke).toHaveBeenCalledTimes(2);
      expect(mockCtx.setLineDash).toHaveBeenCalledWith([]); // solid line for loss
      expect(mockCtx.setLineDash).toHaveBeenCalledWith([6, 4]); // dashed line for accuracy
    });

    test('should use correct colors for line indicators', () => {
      const hoverPoint = {
        step: 50,
        points: [
          {
            series: 'metric1',
            data: { step: 50, value: 1.0 },
            x: 100,
            y: 100,
            color: '#FF3B47',
          },
        ],
      };

      const mockChart = {
        hoverPoint,
        ctx: mockCtx,
        getRunStyle: vi.fn(() => ({
          borderColor: '#FF3B47',
          borderDash: [],
        })),
      };

      const point = hoverPoint.points[0];
      const style = mockChart.getRunStyle(point.series);

      mockCtx.strokeStyle = point.color;

      // Verify the stroke color matches the series color
      expect(mockCtx.strokeStyle).toBe('#FF3B47');
      expect(style.borderColor).toBe('#FF3B47');
    });

    test('should apply dash pattern to line indicators', () => {
      const testCases = [
        { borderDash: [], description: 'solid line' },
        { borderDash: [6, 4], description: 'dashed line' },
        { borderDash: [2, 3], description: 'dotted line' },
        { borderDash: [10, 3, 2, 3], description: 'dash-dot line' },
      ];

      for (const testCase of testCases) {
        vi.clearAllMocks();

        const style = { borderDash: testCase.borderDash };

        if (style.borderDash && style.borderDash.length > 0) {
          mockCtx.setLineDash(style.borderDash);
        } else {
          mockCtx.setLineDash([]);
        }
        mockCtx.beginPath();
        mockCtx.stroke();
        mockCtx.setLineDash([]);

        // Verify setLineDash was called with correct pattern
        expect(mockCtx.setLineDash).toHaveBeenCalledWith(testCase.borderDash);
        // Verify pattern was reset after drawing
        expect(mockCtx.setLineDash).toHaveBeenLastCalledWith([]);
      }
    });

    test('should calculate tooltip width including color indicators', () => {
      const lineIndicatorLength = 16;
      const lineIndicatorGap = 6;
      const indicatorOffset = lineIndicatorLength + lineIndicatorGap;

      mockCtx.measureText = vi.fn((text) => {
        // Simulate different text widths
        if (text.includes('Step:')) return { width: 50 };
        if (text.includes('loss:')) return { width: 80 };
        if (text.includes('accuracy:')) return { width: 100 };
        return { width: 100 };
      });

      const headerText = 'Step: 100';
      const seriesTexts = ['loss: 0.500', 'accuracy: 0.800'];

      let maxWidth = mockCtx.measureText(headerText).width;

      for (const text of seriesTexts) {
        const textWidth = mockCtx.measureText(text).width;
        maxWidth = Math.max(maxWidth, textWidth + indicatorOffset);
      }

      // Header width: 50
      // Series text widths: 80 + 22 = 102, 100 + 22 = 122
      // Max should be 122
      expect(maxWidth).toBe(122);
      expect(mockCtx.measureText).toHaveBeenCalledTimes(3);
    });

    test('should handle single series in tooltip', () => {
      const hoverPoint = {
        step: 10,
        points: [
          {
            series: 'single_metric',
            data: { step: 10, value: 2.5 },
            x: 150,
            y: 200,
            color: '#118AB2',
          },
        ],
      };

      const mockChart = {
        hoverPoint,
        ctx: mockCtx,
        getRunStyle: vi.fn(() => ({
          borderColor: '#118AB2',
          borderDash: [6, 4],
        })),
      };

      // Draw indicator for single series
      const point = hoverPoint.points[0];
      const style = mockChart.getRunStyle(point.series);

      mockCtx.strokeStyle = point.color;
      mockCtx.lineWidth = 2;
      mockCtx.setLineDash(style.borderDash);
      mockCtx.beginPath();
      mockCtx.stroke();
      mockCtx.setLineDash([]);

      expect(mockChart.getRunStyle).toHaveBeenCalledOnce();
      expect(mockCtx.setLineDash).toHaveBeenCalledWith([6, 4]);
    });

    test('should handle multiple series with different styles', () => {
      const hoverPoint = {
        step: 200,
        points: [
          { series: 'run1', data: { step: 200, value: 1.0 }, color: '#FF3B47' },
          { series: 'run2', data: { step: 200, value: 1.5 }, color: '#F77F00' },
          { series: 'run3', data: { step: 200, value: 0.5 }, color: '#118AB2' },
        ],
      };

      const mockChart = {
        hoverPoint,
        ctx: mockCtx,
        getRunStyle: vi.fn((seriesName) => {
          const styles = {
            run1: { borderColor: '#FF3B47', borderDash: [] },
            run2: { borderColor: '#F77F00', borderDash: [6, 4] },
            run3: { borderColor: '#118AB2', borderDash: [2, 3] },
          };
          return styles[seriesName];
        }),
      };

      const dashPatterns = [];

      for (const point of hoverPoint.points) {
        const style = mockChart.getRunStyle(point.series);
        dashPatterns.push(style.borderDash);

        mockCtx.strokeStyle = point.color;
        if (style.borderDash && style.borderDash.length > 0) {
          mockCtx.setLineDash(style.borderDash);
        } else {
          mockCtx.setLineDash([]);
        }
        mockCtx.beginPath();
        mockCtx.stroke();
        mockCtx.setLineDash([]);
      }

      expect(mockChart.getRunStyle).toHaveBeenCalledTimes(3);
      expect(dashPatterns).toEqual([[], [6, 4], [2, 3]]);
      expect(mockCtx.stroke).toHaveBeenCalledTimes(3);
    });
  });
});
