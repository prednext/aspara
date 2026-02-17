/**
 * run-detail.js の統合テスト
 * RunDetailクラスのメソッドをテスト
 */

import { vi } from 'vitest';
import { RunDetail } from '../../src/aspara/dashboard/static/js/pages/run-detail.js';
import { cleanupTestContainer, createTestContainer } from '../vitest-setup.js';

describe('Run Detail Page', () => {
  let container;

  beforeEach(async () => {
    container = createTestContainer();
    container.innerHTML = `
      <div id="metrics-container"></div>
      <div id="chartControls" class="hidden">
        <button id="sizeS">S</button>
        <button id="sizeM">M</button>
        <button id="sizeL">L</button>
      </div>
    `;
  });

  afterEach(() => {
    cleanupTestContainer();
    localStorage.clear();
  });

  describe('RunDetail', () => {
    test('should export RunDetail class', () => {
      expect(RunDetail).toBeDefined();
      expect(typeof RunDetail).toBe('function');
    });
  });

  describe('RunDetail.renderMetrics', () => {
    test('should render charts for each metric', async () => {
      const metricsContainer = document.getElementById('metrics-container');

      // Create a minimal instance without loading data
      const instance = Object.create(RunDetail.prototype);
      instance.chartsContainer = metricsContainer;
      instance.chartControls = document.getElementById('chartControls');
      instance.sizeSBtn = document.getElementById('sizeS');
      instance.sizeMBtn = document.getElementById('sizeM');
      instance.sizeLBtn = document.getElementById('sizeL');
      instance.charts = new Map();
      instance.chartSize = 'M';
      instance.run = 'test_run';

      // Multi-run format: { metricName: { runName: metricData } }
      const metricsData = {
        training_loss: { test_run: { steps: [0, 1], values: [1.0, 0.8] } },
        validation_loss: { test_run: { steps: [0, 1], values: [1.2, 1.0] } },
      };

      instance.renderMetrics(metricsData);

      // Verify charts were created
      expect(instance.charts.size).toBe(2);
      expect(instance.charts.has('training_loss')).toBe(true);
      expect(instance.charts.has('validation_loss')).toBe(true);

      // Verify chart controls are visible
      expect(instance.chartControls.classList.contains('hidden')).toBe(false);
    });

    test('should show no data message when metrics is empty', () => {
      const metricsContainer = document.getElementById('metrics-container');

      const instance = Object.create(RunDetail.prototype);
      instance.chartsContainer = metricsContainer;
      instance.chartControls = document.getElementById('chartControls');
      instance.charts = new Map();
      instance.chartSize = 'M';
      instance.emptyStateMessage = 'No metrics have been recorded for this run.';
      instance.run = 'test_run';

      instance.renderMetrics({});

      expect(instance.charts.size).toBe(0);
      expect(metricsContainer.textContent).toContain('No metrics have been recorded');
      expect(instance.chartControls.classList.contains('hidden')).toBe(true);
    });

    test('should show no data message when metrics is null', () => {
      const metricsContainer = document.getElementById('metrics-container');

      const instance = Object.create(RunDetail.prototype);
      instance.chartsContainer = metricsContainer;
      instance.chartControls = document.getElementById('chartControls');
      instance.charts = new Map();
      instance.chartSize = 'M';
      instance.emptyStateMessage = 'No metrics have been recorded for this run.';
      instance.run = 'test_run';

      instance.renderMetrics(null);

      expect(instance.charts.size).toBe(0);
      expect(metricsContainer.textContent).toContain('No metrics have been recorded');
    });

    test('should handle metric with empty steps', () => {
      const metricsContainer = document.getElementById('metrics-container');

      const instance = Object.create(RunDetail.prototype);
      instance.chartsContainer = metricsContainer;
      instance.chartControls = document.getElementById('chartControls');
      instance.sizeSBtn = document.getElementById('sizeS');
      instance.sizeMBtn = document.getElementById('sizeM');
      instance.sizeLBtn = document.getElementById('sizeL');
      instance.charts = new Map();
      instance.chartSize = 'M';
      instance.run = 'test_run';

      // Multi-run format with empty and valid metrics
      const metricsData = {
        empty_metric: { test_run: { steps: [], values: [] } },
        valid_metric: { test_run: { steps: [0, 1], values: [1.0, 0.8] } },
      };

      instance.renderMetrics(metricsData);

      // Only valid metric should have a chart instance
      expect(instance.charts.size).toBe(1);
      expect(instance.charts.has('valid_metric')).toBe(true);
    });

    test('should clear previous content before rendering', () => {
      const metricsContainer = document.getElementById('metrics-container');
      metricsContainer.innerHTML = '<div class="old-content">Old content</div>';

      const instance = Object.create(RunDetail.prototype);
      instance.chartsContainer = metricsContainer;
      instance.chartControls = document.getElementById('chartControls');
      instance.sizeSBtn = document.getElementById('sizeS');
      instance.sizeMBtn = document.getElementById('sizeM');
      instance.sizeLBtn = document.getElementById('sizeL');
      instance.charts = new Map();
      instance.chartSize = 'M';
      instance.run = 'test_run';

      instance.renderMetrics({ loss: { test_run: { steps: [0], values: [1.0] } } });

      expect(metricsContainer.querySelector('.old-content')).toBeNull();
    });
  });

  describe('RunDetail.showError', () => {
    test('should display error message in container', () => {
      const metricsContainer = document.getElementById('metrics-container');

      const instance = Object.create(RunDetail.prototype);
      instance.chartsContainer = metricsContainer;
      instance.chartControls = document.getElementById('chartControls');

      instance.showError('Test error message');

      expect(metricsContainer.textContent).toContain('An error occurred');
      expect(metricsContainer.textContent).toContain('Test error message');
      expect(metricsContainer.querySelector('.text-red-500')).toBeDefined();
      expect(instance.chartControls.classList.contains('hidden')).toBe(true);
    });
  });
});
