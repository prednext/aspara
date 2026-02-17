/**
 * Run detail page entry point.
 * Orchestrates metric chart rendering for a single run with grid layout.
 */
import { Chart } from '../chart.js';
import { MetricsDataService } from '../metrics/metrics-data-service.js';
import { initNoteEditorFromDOM } from '../note-editor.js';
import { initializeTagEditorsForElements } from '../tag-editor.js';
import { BaseChartPage } from './base-chart-page.js';

/**
 * RunDetail manages the run detail page metrics visualization.
 * Extends BaseChartPage for shared chart layout functionality.
 */
class RunDetail extends BaseChartPage {
  constructor(project, run) {
    super();
    this.project = project;
    this.run = run;
    this.dataService = new MetricsDataService(project);
    this.chartsContainerId = 'metrics-container';
    this.emptyStateMessage = 'No metrics have been recorded for this run.';

    this.init();
    this.initializeTagEditor();
    this.initializeNoteEditor();
    this.loadMetrics();
  }

  initializeTagEditor() {
    initializeTagEditorsForElements('#run-tags-detail', (container) => {
      const projectName = container.dataset.projectName;
      const runName = container.dataset.runName;
      if (!projectName || !runName) return null;
      return `/api/projects/${projectName}/runs/${runName}/metadata`;
    });
  }

  initializeNoteEditor() {
    initNoteEditorFromDOM('run-note');
  }

  async loadMetrics() {
    if (!this.chartsContainer) {
      console.error('Metrics container not found');
      return;
    }

    try {
      await this.dataService.fetchAndCacheMetrics([this.run]);
      const selectedRuns = new Set([this.run]);
      const metricsData = this.dataService.getCachedMetrics(selectedRuns);
      this.renderMetrics(metricsData);
    } catch (error) {
      console.error('Error loading metrics:', error);
      this.showError(error.message);
    }
  }

  initializeChart(chartId, metricName, runData) {
    const metricData = runData[this.run];
    if (!metricData?.steps?.length) {
      return null;
    }

    const chart = new Chart(`#${chartId}`);
    chart.setData({
      series: [{ name: metricName, data: metricData }],
    });
    return chart;
  }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  const detailRoot = document.getElementById('run-detail');
  const project = detailRoot?.dataset.project || window.runData?.project;
  const run = detailRoot?.dataset.run || window.runData?.run;

  if (!project || !run) {
    console.error('Run detail data not found');
    return;
  }

  new RunDetail(project, run);
});

export { RunDetail };
