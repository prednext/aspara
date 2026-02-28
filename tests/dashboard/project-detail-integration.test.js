/**
 * project-detail.js の統合テスト
 * 実際のChartインスタンス作成と連携をテスト
 */

import { encode as msgpackEncode } from '@msgpack/msgpack';
import { vi } from 'vitest';
import { convertToChartFormat } from '../../src/aspara/dashboard/static/js/metrics/metrics-utils.js';
import { ProjectDetail } from '../../src/aspara/dashboard/static/js/pages/project-detail.js';
import { cleanupTestContainer, createTestContainer } from '../vitest-setup.js';

// 外部依存のみをモック
global.fetch = vi.fn();

describe('ProjectMetrics Integration', () => {
  let container;
  let projectDetail;

  beforeEach(async () => {
    container = createTestContainer();
    container.innerHTML = `
      <input type="text" id="runFilter" placeholder="Filter runs">
      <span id="selectedCount">0</span>

      <div id="runs-list-container">
        <div class="run-item" data-run-name="run_1" data-run-last-update="2024-01-01T00:00:00Z">
          <label>
            <input type="checkbox" class="run-checkbox" data-run-name="run_1">
            <span>Run 1</span>
          </label>
        </div>
        <div class="run-item" data-run-name="run_2" data-run-last-update="2024-01-01T00:00:00Z">
          <label>
            <input type="checkbox" class="run-checkbox" data-run-name="run_2">
            <span>Run 2</span>
          </label>
        </div>
      </div>

      <div id="initialState" class="hidden"></div>
      <div id="loadingState" class="hidden"></div>
      <div id="chartsContainer"></div>
      <div id="noDataState" class="hidden"></div>
      <div id="chartControls" class="hidden"></div>
    `;

    // fetchのモック設定 (metric-first delta-compressed array format)
    const responseData = {
      project: 'test_project',
      metrics: {
        training_loss: {
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
    };

    const encoded = msgpackEncode(responseData);
    const arrayBuffer = encoded.buffer.slice(encoded.byteOffset, encoded.byteOffset + encoded.byteLength);

    fetch.mockResolvedValue({
      ok: true,
      arrayBuffer: () => Promise.resolve(arrayBuffer),
    });

    // URL mockを設定
    Object.defineProperty(window, 'location', {
      value: {
        pathname: '/projects/test_project',
      },
      writable: true,
    });

    projectDetail = new ProjectDetail();
  });

  afterEach(() => {
    cleanupTestContainer();
    fetch.mockClear();
  });

  describe('Chart Instance Creation', () => {
    test('ProjectDetail should create Chart instances for each metric', async () => {
      // ランを選択
      const checkbox1 = document.querySelector('.run-checkbox[data-run-name="run_1"]');
      const checkbox2 = document.querySelector('.run-checkbox[data-run-name="run_2"]');

      checkbox1.checked = true;
      checkbox1.dispatchEvent(new Event('change'));
      checkbox2.checked = true;
      checkbox2.dispatchEvent(new Event('change'));

      await projectDetail.showMetrics();

      // API呼び出しが正しく行われることを確認
      expect(fetch).toHaveBeenCalledWith('/api/projects/test_project/runs/metrics?runs=run_1%2Crun_2&format=msgpack');

      // チャートが実際に作成されることを確認
      const chartsContainer = document.getElementById('chartsContainer');
      const chartContainers = chartsContainer.querySelectorAll('.bg-base-surface');
      expect(chartContainers.length).toBe(2); // training_loss, accuracy
    });

    test('should handle API errors gracefully', async () => {
      // Clear cache to force a new fetch
      projectDetail.dataService.metricsCache = {};
      projectDetail.dataService.cachedRuns.clear();

      fetch.mockRejectedValueOnce(new Error('API error'));

      await projectDetail.showMetrics();

      const noDataState = document.getElementById('noDataState');
      expect(noDataState.classList.contains('hidden')).toBe(false);
    });

    test('should handle empty data', async () => {
      // Clear cache to force a new fetch
      projectDetail.dataService.metricsCache = {};
      projectDetail.dataService.cachedRuns.clear();

      const emptyResponse = { project: 'test_project', metrics: {} };
      const encoded = msgpackEncode(emptyResponse);
      const arrayBuffer = encoded.buffer.slice(encoded.byteOffset, encoded.byteOffset + encoded.byteLength);

      fetch.mockResolvedValueOnce({
        ok: true,
        arrayBuffer: () => Promise.resolve(arrayBuffer),
      });

      await projectDetail.showMetrics();

      const noDataState = document.getElementById('noDataState');
      expect(noDataState.classList.contains('hidden')).toBe(false);
    });
  });

  describe('Multi-Run Data Processing', () => {
    test('should convert data to chart format with proper series structure', () => {
      // SoA format input
      const runData = {
        run_1: {
          steps: [0, 1],
          values: [1.0, 0.8],
          timestamps: [1000, 2000],
        },
        run_2: {
          steps: [0, 1],
          values: [1.2, 0.9],
          timestamps: [1000, 2000],
        },
      };

      const chartData = convertToChartFormat('test_metric', runData);

      expect(chartData.title).toBe('test_metric');
      expect(chartData.series).toHaveLength(2);
      expect(chartData.series[0].name).toBe('run_1');
      expect(chartData.series[1].name).toBe('run_2');
      // SoA format output
      expect(chartData.series[0].data).toEqual({
        steps: [0, 1],
        values: [1.0, 0.8],
      });
    });
  });

  describe('Run Selection Logic', () => {
    test('should track selected runs', () => {
      const checkbox1 = document.querySelector('.run-checkbox[data-run-name="run_1"]');

      checkbox1.checked = true;
      checkbox1.dispatchEvent(new Event('change'));

      expect(projectDetail.runSelector.getSelectedRuns().has('run_1')).toBe(true);
    });

    test('should track manually deselected runs', () => {
      const checkbox1 = document.querySelector('.run-checkbox[data-run-name="run_1"]');

      // Initially selected (from loadInitialData)
      expect(projectDetail.runSelector.getSelectedRuns().has('run_1')).toBe(true);

      // Manually deselect
      checkbox1.checked = false;
      checkbox1.dispatchEvent(new Event('change'));

      expect(projectDetail.runSelector.getSelectedRuns().has('run_1')).toBe(false);
      expect(projectDetail.runSelector.manuallyDeselectedRuns.has('run_1')).toBe(true);
    });

    test('should update selected count correctly', () => {
      const checkbox1 = document.querySelector('.run-checkbox[data-run-name="run_1"]');
      const checkbox2 = document.querySelector('.run-checkbox[data-run-name="run_2"]');
      const selectedCountSpan = document.getElementById('selectedCount');

      // Initially all runs are selected
      expect(selectedCountSpan.textContent).toBe('2');

      checkbox1.checked = false;
      checkbox1.dispatchEvent(new Event('change'));
      expect(selectedCountSpan.textContent).toBe('1');

      checkbox2.checked = false;
      checkbox2.dispatchEvent(new Event('change'));
      expect(selectedCountSpan.textContent).toBe('0');

      checkbox1.checked = true;
      checkbox1.dispatchEvent(new Event('change'));
      expect(selectedCountSpan.textContent).toBe('1');
    });

    test('should auto-reload metrics when checkbox changes and charts are visible', async () => {
      const checkbox1 = document.querySelector('.run-checkbox[data-run-name="run_1"]');
      const checkbox2 = document.querySelector('.run-checkbox[data-run-name="run_2"]');

      // Verify charts are created from initial load
      expect(projectDetail.charts.size).toBeGreaterThan(0);

      // Clear cache and record initial fetch count
      projectDetail.dataService.metricsCache = {};
      projectDetail.dataService.cachedRuns.clear();
      const initialFetchCount = fetch.mock.calls.length;

      // Change checkbox - should trigger auto-reload with new fetch
      checkbox2.checked = false;
      checkbox2.dispatchEvent(new Event('change'));

      // Wait for the async showMetrics to complete
      await vi.waitFor(() => {
        expect(fetch.mock.calls.length).toBeGreaterThan(initialFetchCount);
      });
    });
  });

  describe('Run Filtering', () => {
    test('should filter runs by regex pattern', () => {
      projectDetail.runSelector.filterRuns('run_1');

      const runItem1 = document.querySelector('[data-run-name="run_1"]').closest('.run-item');
      const runItem2 = document.querySelector('[data-run-name="run_2"]').closest('.run-item');

      expect(runItem1.style.display).toBe('');
      expect(runItem2.style.display).toBe('none');
    });

    test('should auto-select filtered runs', () => {
      const checkbox1 = document.querySelector('.run-checkbox[data-run-name="run_1"]');
      const checkbox2 = document.querySelector('.run-checkbox[data-run-name="run_2"]');

      // Deselect all first and mark as manually deselected
      checkbox1.checked = false;
      checkbox1.dispatchEvent(new Event('change'));
      checkbox2.checked = false;
      checkbox2.dispatchEvent(new Event('change'));

      // Clear manually deselected state for run_1 to allow auto-selection
      projectDetail.runSelector.manuallyDeselectedRuns.delete('run_1');

      // Filter should auto-select matching runs (that are not manually deselected)
      projectDetail.runSelector.filterRuns('run_1');

      expect(checkbox1.checked).toBe(true);
      expect(projectDetail.runSelector.getSelectedRuns().has('run_1')).toBe(true);
    });

    test('should respect manually deselected runs during filtering', () => {
      const checkbox1 = document.querySelector('.run-checkbox[data-run-name="run_1"]');

      // Manually deselect
      checkbox1.checked = false;
      checkbox1.dispatchEvent(new Event('change'));

      // Filter should not auto-select manually deselected runs
      projectDetail.runSelector.filterRuns('run');

      expect(checkbox1.checked).toBe(false);
      expect(projectDetail.runSelector.getSelectedRuns().has('run_1')).toBe(false);
    });

    test('should handle invalid regex gracefully', () => {
      // Invalid regex pattern
      projectDetail.runSelector.filterRuns('[invalid');

      // Should show all runs
      const runItem1 = document.querySelector('[data-run-name="run_1"]');
      const runItem2 = document.querySelector('[data-run-name="run_2"]');

      expect(runItem1.style.display).toBe('');
      expect(runItem2.style.display).toBe('');
    });
  });

  describe('Chart Creation Integration', () => {
    test('should create separate charts for each unique metric', async () => {
      const checkbox1 = document.querySelector('.run-checkbox[data-run-name="run_1"]');
      const checkbox2 = document.querySelector('.run-checkbox[data-run-name="run_2"]');

      checkbox1.checked = true;
      checkbox1.dispatchEvent(new Event('change'));
      checkbox2.checked = true;
      checkbox2.dispatchEvent(new Event('change'));

      await projectDetail.showMetrics();

      const chartsContainer = document.getElementById('chartsContainer');
      const chartContainers = chartsContainer.querySelectorAll('.bg-base-surface');

      // チャートコンテナが作成されることを確認
      expect(chartContainers.length).toBe(2);

      const chartTitles = Array.from(chartsContainer.querySelectorAll('h3')).map((h) => h.textContent);
      expect(chartTitles).toContain('training_loss');
      expect(chartTitles).toContain('accuracy');
    });

    test('should handle chart creation failures gracefully', async () => {
      // Clear cache to force a new fetch
      projectDetail.dataService.metricsCache = {};
      projectDetail.dataService.cachedRuns.clear();

      // APIエラーをシミュレート
      const errorResponse = { error: 'API Error occurred' };
      const encoded = msgpackEncode(errorResponse);
      const arrayBuffer = encoded.buffer.slice(encoded.byteOffset, encoded.byteOffset + encoded.byteLength);

      fetch.mockResolvedValueOnce({
        ok: true,
        arrayBuffer: () => Promise.resolve(arrayBuffer),
      });

      await projectDetail.showMetrics();

      const noDataState = document.getElementById('noDataState');
      // エラー時には noDataState が表示されることを確認
      expect(noDataState.classList.contains('hidden')).toBe(false);
    });

    test('should clear previous charts when showing new metrics', async () => {
      const checkbox1 = document.querySelector('.run-checkbox[data-run-name="run_1"]');
      checkbox1.checked = true;
      checkbox1.dispatchEvent(new Event('change'));

      await projectDetail.showMetrics();

      const chartsContainer = document.getElementById('chartsContainer');
      const firstChartCount = chartsContainer.querySelectorAll('.bg-base-surface').length;

      // Show metrics again
      await projectDetail.showMetrics();

      const secondChartCount = chartsContainer.querySelectorAll('.bg-base-surface').length;

      // Should have same number of charts (old ones cleared)
      expect(secondChartCount).toBe(firstChartCount);
    });
  });

  describe('Initial State', () => {
    test('should auto-load metrics on page load if runs exist', () => {
      // This is tested by the constructor behavior
      expect(projectDetail.runSelector.getSelectedRuns().size).toBe(2);
      expect(projectDetail.runSelector.allRuns).toEqual(['run_1', 'run_2']);
    });

    test('should extract project from URL', () => {
      expect(projectDetail.currentProject).toBe('test_project');
    });
  });
});
