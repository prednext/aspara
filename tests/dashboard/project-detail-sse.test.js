import { encode as msgpackEncode } from '@msgpack/msgpack';
/**
 * Tests for ProjectDetail SSE functionality
 */
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { ProjectDetail } from '../../src/aspara/dashboard/static/js/pages/project-detail.js';
import { cleanupTestContainer, createTestContainer, mockFetch } from '../vitest-setup.js';

describe('ProjectMetrics SSE Integration', () => {
  let projectDetail;

  beforeEach(() => {
    // Setup EventSource mock with proper close method
    const mockEventSource = vi.fn().mockImplementation(function (url) {
      const instance = {
        url,
        readyState: 1, // OPEN
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        close: vi.fn(() => {
          instance.readyState = 2; // CLOSED
        }),
      };
      return instance;
    });
    global.EventSource = mockEventSource;

    createTestContainer();

    // Setup DOM structure for ProjectDetail
    document.body.innerHTML = `
      <div id="test-container">
        <input id="runFilter" type="text" />
        <button id="showButton">Show</button>
        <span id="selectedCount">0</span>
        <div id="loadingState" class="hidden">Loading...</div>
        <div id="chartsContainer" class="hidden"></div>
        <div id="noDataState" class="hidden">No data</div>
        <div id="initialState">Select runs</div>
        <div id="chartControls" class="hidden">
          <button id="layout1Col">1 Col</button>
          <button id="layout2Col">2 Col</button>
          <button id="sizeS">S</button>
          <button id="sizeM">M</button>
          <button id="sizeL">L</button>
          <input id="syncZoom" type="checkbox" />
        </div>
        <div class="run-item">
          <input type="checkbox" class="run-checkbox" data-run-name="run_1" />
          <span>run_1</span>
        </div>
        <div class="run-item">
          <input type="checkbox" class="run-checkbox" data-run-name="run_2" />
          <span>run_2</span>
        </div>
      </div>
    `;

    // Mock window.location
    Object.defineProperty(window, 'location', {
      value: { pathname: '/projects/test_project' },
      writable: true,
    });

    // Setup fetch mock with metric-first delta-compressed array format
    mockFetch({
      project: 'test_project',
      metrics: {
        loss: {
          run_1: {
            steps: [0, 1], // delta-compressed: [0, +1]
            values: [1.0, 0.8],
            timestamps: [1735732800000, 60000], // unix time ms, delta-compressed: [absolute, +60000ms]
          },
          run_2: {
            steps: [0, 1],
            values: [1.2, 0.9],
            timestamps: [1735732800000, 60000],
          },
        },
        accuracy: {
          run_1: {
            steps: [0, 1],
            values: [0.7, 0.8],
            timestamps: [1735732800000, 60000],
          },
          run_2: {
            steps: [0, 1],
            values: [0.6, 0.75],
            timestamps: [1735732800000, 60000],
          },
        },
      },
    });

    projectDetail = new ProjectDetail();
  });

  afterEach(() => {
    cleanupTestContainer();
    vi.restoreAllMocks();
  });

  describe('setupSSE', () => {
    test('should create EventSource with correct URL', () => {
      projectDetail.currentProject = 'test_project';
      // Reset lastSSETimestamp to test URL format with explicit since value
      projectDetail.dataService.lastSSETimestamp = 0;

      // Setup SSE
      projectDetail.dataService.setupSSE('run_1,run_2');

      // Verify EventSource was created
      expect(global.EventSource).toHaveBeenCalled();
      const eventSourceCall = global.EventSource.mock.calls[global.EventSource.mock.calls.length - 1];
      // URL should include since parameter based on lastSSETimestamp
      expect(eventSourceCall[0]).toBe('/api/projects/test_project/runs/stream?runs=run_1%2Crun_2&since=0');

      // Verify the eventSource has a close method
      expect(projectDetail.dataService.eventSource.close).toBeDefined();
      expect(typeof projectDetail.dataService.eventSource.close).toBe('function');
    });

    test('should close existing EventSource before creating new one', () => {
      projectDetail.currentProject = 'test_project';

      // Create first EventSource
      projectDetail.dataService.setupSSE('run_1');
      const firstEventSource = projectDetail.dataService.eventSource;

      // Create second EventSource
      projectDetail.dataService.setupSSE('run_2');

      // Verify first EventSource was closed
      expect(firstEventSource.close).toHaveBeenCalled();
    });

    test('should register metric event listener', () => {
      projectDetail.currentProject = 'test_project';

      projectDetail.dataService.setupSSE('run_1');

      // Verify event listener was registered
      expect(projectDetail.dataService.eventSource.addEventListener).toHaveBeenCalledWith('metric', expect.any(Function));
    });

    test('should register error event listener', () => {
      projectDetail.currentProject = 'test_project';

      projectDetail.dataService.setupSSE('run_1');

      // Verify error listener was registered
      expect(projectDetail.dataService.eventSource.addEventListener).toHaveBeenCalledWith('error', expect.any(Function));
    });
  });

  describe('closeSSE', () => {
    test('should close EventSource if exists', () => {
      projectDetail.currentProject = 'test_project';
      projectDetail.dataService.setupSSE('run_1');

      const eventSource = projectDetail.dataService.eventSource;

      projectDetail.dataService.closeSSE();

      expect(eventSource.close).toHaveBeenCalled();
      expect(projectDetail.dataService.eventSource).toBeNull();
    });

    test('should not throw if EventSource does not exist', () => {
      projectDetail.dataService.eventSource = null;

      expect(() => projectDetail.dataService.closeSSE()).not.toThrow();
    });
  });

  describe('handleMetricUpdate', () => {
    beforeEach(async () => {
      // Setup initial chart state
      projectDetail.runSelector.selectedRuns.add('run_1');
      projectDetail.currentProject = 'test_project';

      // Mock fetch to return metrics data (metric-first delta-compressed array format)
      const responseData = {
        project: 'test_project',
        metrics: {
          loss: {
            run_1: {
              steps: [0],
              values: [1.0],
              timestamps: [1735732800000], // unix time ms
            },
          },
        },
      };

      const encoded = msgpackEncode(responseData);
      const arrayBuffer = encoded.buffer.slice(encoded.byteOffset, encoded.byteOffset + encoded.byteLength);

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        arrayBuffer: () => Promise.resolve(arrayBuffer),
      });

      await projectDetail.showMetrics();
    });

    test('should update existing chart with new data point', () => {
      // Get the chart for 'loss' metric
      const lossChart = projectDetail.charts.get('loss');
      expect(lossChart).toBeDefined();

      // Spy on addDataPoint
      const addDataPointSpy = vi.spyOn(lossChart, 'addDataPoint');

      // Simulate SSE metric update
      const newMetric = {
        run: 'run_1',
        step: 1,
        metrics: { loss: 0.8 },
      };

      projectDetail.dataService.handleMetricUpdate(newMetric);

      // Verify addDataPoint was called
      expect(addDataPointSpy).toHaveBeenCalledWith('run_1', 1, 0.8);
    });

    test('should handle multiple metrics in single update', async () => {
      const responseData = {
        project: 'test_project',
        metrics: {
          loss: {
            run_1: {
              steps: [0],
              values: [1.0],
              timestamps: [1735732800000], // unix time ms
            },
          },
          accuracy: {
            run_1: {
              steps: [0],
              values: [0.5],
              timestamps: [1735732800000], // unix time ms
            },
          },
        },
      };

      const encoded = msgpackEncode(responseData);
      const arrayBuffer = encoded.buffer.slice(encoded.byteOffset, encoded.byteOffset + encoded.byteLength);

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        arrayBuffer: () => Promise.resolve(arrayBuffer),
      });

      // Re-render to create both charts
      await projectDetail.showMetrics();

      const lossChart = projectDetail.charts.get('loss');
      const accuracyChart = projectDetail.charts.get('accuracy');

      expect(lossChart).toBeDefined();
      expect(accuracyChart).toBeDefined();

      const lossChartSpy = vi.spyOn(lossChart, 'addDataPoint');
      const accuracyChartSpy = vi.spyOn(accuracyChart, 'addDataPoint');

      // Simulate SSE metric update with multiple metrics
      const newMetric = {
        run: 'run_1',
        step: 1,
        metrics: {
          loss: 0.8,
          accuracy: 0.6,
        },
      };

      projectDetail.dataService.handleMetricUpdate(newMetric);

      // Verify both charts were updated
      expect(lossChartSpy).toHaveBeenCalledWith('run_1', 1, 0.8);
      expect(accuracyChartSpy).toHaveBeenCalledWith('run_1', 1, 0.6);
    });

    test('should ignore metrics without run field', async () => {
      // Setup: Add run to selectedRuns and load metrics to create charts
      projectDetail.runSelector.selectedRuns.add('run_1');
      await projectDetail.showMetrics();

      const lossChart = projectDetail.charts.get('loss');
      const addDataPointSpy = vi.spyOn(lossChart, 'addDataPoint');

      // Metric without run field
      const invalidMetric = {
        step: 1,
        metrics: { loss: 0.8 },
      };

      projectDetail.dataService.handleMetricUpdate(invalidMetric);

      // Verify addDataPoint was NOT called
      expect(addDataPointSpy).not.toHaveBeenCalled();
    });

    test('should ignore metrics without metrics field', async () => {
      // Setup: Add run to selectedRuns and load metrics to create charts
      projectDetail.runSelector.selectedRuns.add('run_1');
      await projectDetail.showMetrics();

      const lossChart = projectDetail.charts.get('loss');
      const addDataPointSpy = vi.spyOn(lossChart, 'addDataPoint');

      // Metric without metrics field
      const invalidMetric = {
        run: 'run_1',
        step: 1,
      };

      projectDetail.dataService.handleMetricUpdate(invalidMetric);

      // Verify addDataPoint was NOT called
      expect(addDataPointSpy).not.toHaveBeenCalled();
    });

    test('should skip metrics that do not have corresponding charts', () => {
      // Simulate metric for chart that doesn't exist
      const newMetric = {
        run: 'run_1',
        step: 1,
        metrics: {
          unknown_metric: 0.5,
        },
      };

      // Should not throw
      expect(() => projectDetail.dataService.handleMetricUpdate(newMetric)).not.toThrow();
    });

    test('should handle metric update with default step', async () => {
      // Setup: Add run to selectedRuns and load metrics to create charts
      projectDetail.runSelector.selectedRuns.add('run_1');
      await projectDetail.showMetrics();

      const lossChart = projectDetail.charts.get('loss');
      const addDataPointSpy = vi.spyOn(lossChart, 'addDataPoint');

      // Metric without step field
      const metricWithoutStep = {
        run: 'run_1',
        metrics: { loss: 0.8 },
      };

      projectDetail.dataService.handleMetricUpdate(metricWithoutStep);

      // Verify addDataPoint was called with step=0 (default)
      expect(addDataPointSpy).toHaveBeenCalledWith('run_1', 0, 0.8);
    });
  });

  describe('SSE Integration with showMetrics', () => {
    test('should setup SSE after loading initial metrics', async () => {
      projectDetail.runSelector.selectedRuns.add('run_1');
      projectDetail.currentProject = 'test_project';

      const responseData = {
        project: 'test_project',
        metrics: {
          loss: {
            run_1: {
              steps: [0],
              values: [1.0],
              timestamps: [1735732800000], // unix time ms
            },
          },
        },
      };

      const encoded = msgpackEncode(responseData);
      const arrayBuffer = encoded.buffer.slice(encoded.byteOffset, encoded.byteOffset + encoded.byteLength);

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        arrayBuffer: () => Promise.resolve(arrayBuffer),
      });

      await projectDetail.showMetrics();

      // Verify SSE was setup
      expect(global.EventSource).toHaveBeenCalled();
      expect(projectDetail.dataService.eventSource).not.toBeNull();
    });

    test('should close SSE when no runs selected', async () => {
      projectDetail.runSelector.selectedRuns.add('run_1');
      projectDetail.currentProject = 'test_project';

      const responseData = {
        project: 'test_project',
        metrics: {
          loss: {
            run_1: {
              steps: [0],
              values: [1.0],
              timestamps: [1735732800000], // unix time ms
            },
          },
        },
      };

      const encoded = msgpackEncode(responseData);
      const arrayBuffer = encoded.buffer.slice(encoded.byteOffset, encoded.byteOffset + encoded.byteLength);

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        arrayBuffer: () => Promise.resolve(arrayBuffer),
      });

      await projectDetail.showMetrics();

      // Clear selection
      projectDetail.runSelector.selectedRuns.clear();
      await projectDetail.showMetrics();

      // Verify SSE was closed
      expect(projectDetail.dataService.eventSource).toBeNull();
    });
  });
});
