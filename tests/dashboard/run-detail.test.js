/**
 * Unit tests for RunDetail
 */

import { beforeEach, describe, expect, test, vi } from 'vitest';

// Mock all dependencies
const mockChartSetData = vi.fn();
vi.mock('../../src/aspara/dashboard/static/js/chart.js', () => ({
  Chart: class {
    constructor() {
      this.setData = mockChartSetData;
    }
  },
}));
vi.mock('../../src/aspara/dashboard/static/js/metrics/metrics-data-service.js', () => ({
  MetricsDataService: class {
    constructor() {
      this.fetchAndCacheMetrics = vi.fn().mockResolvedValue({});
      this.getCachedMetrics = vi.fn().mockReturnValue({});
    }
  },
}));
vi.mock('../../src/aspara/dashboard/static/js/note-editor.js', () => ({
  initNoteEditorFromDOM: vi.fn(),
}));
vi.mock('../../src/aspara/dashboard/static/js/tag-editor.js', () => ({
  initializeTagEditorsForElements: vi.fn(),
}));
vi.mock('../../src/aspara/dashboard/static/js/metrics/chart-layout.js', () => ({
  CHART_SIZE_KEY: 'chart-size',
  applyGridLayout: vi.fn(),
  calculateChartDimensions: vi.fn(() => ({ columns: 1, chartWidth: 400, chartHeight: 225, gap: 32 })),
  updateChartHeights: vi.fn(),
  updateContainerPadding: vi.fn(),
  updateSizeButtonStyles: vi.fn(),
}));
vi.mock('../../src/aspara/dashboard/static/js/metrics/metric-chart-factory.js', () => ({
  createChartErrorDisplay: vi.fn(() => document.createElement('div')),
  createMetricChartContainer: vi.fn(() => ({
    container: document.createElement('div'),
    chartId: 'chart-1',
  })),
}));
vi.mock('../../src/aspara/dashboard/static/js/html-utils.js', () => ({
  escapeHtml: vi.fn((s) => s),
}));

import { RunDetail } from '../../src/aspara/dashboard/static/js/pages/run-detail.js';

describe('RunDetail', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="metrics-container"></div>
      <div id="run-tags-detail" data-project-name="proj" data-run-name="run1"></div>
      <div id="run-note"></div>
    `;
    localStorage.clear();
    vi.clearAllMocks();
  });

  describe('initializeChart', () => {
    test('should return null when no metric data for run', () => {
      const rd = new RunDetail('proj', 'run1');
      const result = rd.initializeChart('chart-1', 'loss', {});

      expect(result).toBeNull();
    });

    test('should return null when metric data has empty steps', () => {
      const rd = new RunDetail('proj', 'run1');
      const result = rd.initializeChart('chart-1', 'loss', {
        run1: { steps: [], values: [] },
      });

      expect(result).toBeNull();
    });

    test('should create chart when valid data exists', () => {
      const rd = new RunDetail('proj', 'run1');

      const result = rd.initializeChart('chart-1', 'loss', {
        run1: { steps: [0, 1, 2], values: [0.5, 0.3, 0.1] },
      });

      expect(result).not.toBeNull();
      expect(mockChartSetData).toHaveBeenCalledWith({
        series: [{ name: 'loss', data: { steps: [0, 1, 2], values: [0.5, 0.3, 0.1] } }],
      });
    });

    test('should return null when run data is undefined', () => {
      const rd = new RunDetail('proj', 'run1');
      const result = rd.initializeChart('chart-1', 'loss', {
        otherRun: { steps: [0], values: [1] },
      });

      expect(result).toBeNull();
    });
  });
});
