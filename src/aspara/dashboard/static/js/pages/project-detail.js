/**
 * Project detail page entry point.
 * Orchestrates run selection, metrics visualization, and real-time updates.
 */
import { Chart } from '../chart.js';
import { RunSelector } from '../components/run-selector.js';
import { SSEStatusIndicator } from '../components/sse-status-indicator.js';
import { registerPageLifecycle } from '../lifecycle.js';
import { MetricsDataService } from '../metrics/metrics-data-service.js';
import { convertToChartFormat } from '../metrics/metrics-utils.js';
import { initNoteEditorFromDOM } from '../note-editor.js';
import { updateRunStatusIcon } from '../runs-list/sse-utils.js';
import { BaseChartPage, CHART_SIZE_KEY } from './base-chart-page.js';

// LocalStorage keys
const SIDEBAR_COLLAPSED_KEY = 'aspara-sidebar-collapsed';

/**
 * ProjectDetail manages the project detail page.
 * Extends BaseChartPage for shared chart layout functionality.
 */
class ProjectDetail extends BaseChartPage {
  constructor() {
    super();
    this.currentProject = '';
    this.syncZoom = localStorage.getItem('sync_zoom') === 'true';
    this.globalZoomState = null;
    this.dataService = null;
    this.runSelector = null;
    this.sseIndicator = null;

    // Project-specific event handlers (stored for cleanup in destroy())
    this.syncZoomHandler = null;
    this.sidebarToggleHandler = null;

    // Monotonic ID used to discard stale showMetrics() results.
    // Incremented on every showMetrics() invocation; the in-flight request
    // captures the ID and bails out after `await` if a newer request has
    // superseded it.
    this._metricsRequestId = 0;

    // Note editor instance (stored for cleanup in destroy())
    this.noteEditor = null;

    this.init();
    this.setupProjectSpecificListeners();
    this.initializeNoteEditor();
    this.loadInitialData();
  }

  async initializeNoteEditor() {
    this.noteEditor = await initNoteEditorFromDOM('project-note');
  }

  initializeElements() {
    super.initializeElements();

    this.loadingState = document.getElementById('loadingState');
    this.noDataState = document.getElementById('noDataState');
    this.initialState = document.getElementById('initialState');
    this.syncZoomCheckbox = document.getElementById('syncZoom');

    // Sidebar elements
    this.sidebar = document.getElementById('runs-sidebar');
    this.toggleSidebarBtn = document.getElementById('toggleSidebar');
    this.sidebarCollapseIcon = document.getElementById('sidebar-collapse-icon');
    this.sidebarExpandIcon = document.getElementById('sidebar-expand-icon');
    this.sidebarExpandedContent = document.getElementById('sidebar-expanded-content');
    this.sidebarCollapsedContent = document.getElementById('sidebar-collapsed-content');
    this.sidebarTitle = document.getElementById('sidebar-title');
  }

  setupProjectSpecificListeners() {
    // Setup sync zoom event listener
    if (this.syncZoomCheckbox) {
      this.syncZoomCheckbox.checked = this.syncZoom;
      this.syncZoomHandler = (e) => {
        this.syncZoom = e.target.checked;
        localStorage.setItem('sync_zoom', this.syncZoom);
        if (!this.syncZoom) {
          this.globalZoomState = null;
        }
      };
      this.syncZoomCheckbox.addEventListener('change', this.syncZoomHandler);
    }

    // Setup sidebar toggle
    this.initSidebarToggle();
  }

  initSidebarToggle() {
    if (!this.sidebar || !this.toggleSidebarBtn) return;

    const isCollapsed = localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true';
    if (isCollapsed) {
      this.collapseSidebar();
    }

    this.sidebarToggleHandler = () => {
      const collapsed = this.sidebar.dataset.collapsed === 'true';
      if (collapsed) {
        this.expandSidebar();
      } else {
        this.collapseSidebar();
      }
    };
    this.toggleSidebarBtn.addEventListener('click', this.sidebarToggleHandler);
  }

  _setSidebarCollapsed(collapsed) {
    if (!this.sidebar) return;

    this.sidebar.dataset.collapsed = String(collapsed);
    this.sidebar.classList.toggle('w-80', !collapsed);
    this.sidebar.classList.toggle('w-16', collapsed);

    this.sidebarCollapseIcon?.classList.toggle('hidden', collapsed);
    this.sidebarExpandIcon?.classList.toggle('hidden', !collapsed);
    this.sidebarExpandedContent?.classList.toggle('hidden', collapsed);
    this.sidebarCollapsedContent?.classList.toggle('hidden', !collapsed);
    this.sidebarTitle?.classList.toggle('hidden', collapsed);

    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
    this.resizeChartsAfterTransition();
  }

  collapseSidebar() {
    this._setSidebarCollapsed(true);
  }

  expandSidebar() {
    this._setSidebarCollapsed(false);
  }

  /**
   * Toggle the visibility of the four main UI sections by page state.
   * @param {'initial'|'loading'|'noData'|'metrics'} state - Page state name
   */
  _setPageState(state) {
    const hidden = {
      initial: { loading: true, charts: true, noData: true, initial: false },
      loading: { loading: false, charts: true, noData: true, initial: true },
      noData: { loading: true, charts: true, noData: false, initial: true },
      metrics: { loading: true, charts: false, noData: true, initial: true },
    }[state];
    if (!hidden) return;
    this.loadingState.classList.toggle('hidden', hidden.loading);
    this.chartsContainer.classList.toggle('hidden', hidden.charts);
    this.noDataState.classList.toggle('hidden', hidden.noData);
    this.initialState.classList.toggle('hidden', hidden.initial);
  }

  resizeChartsAfterTransition() {
    if (!this.sidebar) return;

    const handleTransitionEnd = (e) => {
      if (e.target !== this.sidebar || e.propertyName !== 'width') return;
      this.sidebar.removeEventListener('transitionend', handleTransitionEnd);
      this.applyAutoLayout();
    };

    this.sidebar.addEventListener('transitionend', handleTransitionEnd);

    setTimeout(() => {
      this.sidebar.removeEventListener('transitionend', handleTransitionEnd);
      this.applyAutoLayout();
    }, 250);
  }

  loadInitialData() {
    // Extract project from URL (/projects/{project})
    const pathParts = window.location.pathname.split('/');
    if (pathParts.length >= 3) {
      this.currentProject = pathParts[2];
    }

    // Initialize SSE status indicator
    this.sseIndicator = new SSEStatusIndicator('sse-status');

    // Initialize data service
    this.dataService = new MetricsDataService(this.currentProject, {
      onMetricUpdate: (metricName, runName, step, value) => {
        if (!this.runSelector?.getSelectedRuns().has(runName)) {
          return;
        }
        const chart = this.charts.get(metricName);
        if (chart) {
          chart.addDataPoint(runName, step, value);
        }
        this.sseIndicator?.recordEvent();
      },
      onStatusUpdate: (statusData) => this.handleStatusUpdate(statusData),
      onCacheUpdated: () => this.renderMetricsFromCache(),
      onConnectionStateChange: (state, detail) => {
        if (!this.sseIndicator) return;
        if (state === 'connected') {
          this.sseIndicator.setConnected();
        } else if (state === 'reconnecting') {
          this.sseIndicator.setReconnecting(detail.attempt ?? 0, detail.max ?? 0);
        } else if (state === 'disconnected') {
          this.sseIndicator.setDisconnected(detail.lastEventTime ?? 0);
        }
      },
    });

    // Initialize run selector
    this.runSelector = new RunSelector({
      onSelectionChange: (selectedRuns) => this.showMetrics(),
    });

    // Auto-load metrics if runs exist
    if (this.runSelector.getSelectedRuns().size > 0) {
      this.showMetrics();
    } else {
      this.showInitialState();
    }
  }

  showInitialState() {
    this._setPageState('initial');
    this.clearAndRenderCharts({});
    this.runSelector.hideAllLegends();
    this.hideChartControls();
  }

  showLoadingState() {
    this._setPageState('loading');
  }

  async showMetrics() {
    const selectedRuns = this.runSelector.getSelectedRuns();

    if (selectedRuns.size === 0) {
      this.showInitialState();
      this.dataService.closeSSE();
      return;
    }

    // Assign a fresh ID to this invocation so that any earlier in-flight
    // showMetrics() call can detect it has been superseded and bail out
    // before rendering or setting up SSE with stale data.
    const requestId = ++this._metricsRequestId;

    const runsToFetch = this.dataService.getRunsToFetch(selectedRuns);
    this.dataService.adjustCacheSize(selectedRuns.size);

    if (runsToFetch.length > 0) {
      this.showLoadingState();
      try {
        await this.dataService.fetchAndCacheMetrics(runsToFetch);
      } catch (error) {
        // Only surface the error if this is still the latest request;
        // otherwise a newer selection change owns the UI state.
        if (requestId === this._metricsRequestId) {
          console.error('Error loading metrics:', error);
          this.showErrorState(error.message);
        }
        return;
      }

      // A newer showMetrics() invocation has superseded this one; discard
      // the stale result to avoid overwriting fresh UI state.
      if (requestId !== this._metricsRequestId) {
        return;
      }
    }

    this.renderMetricsFromCache();
  }

  renderMetricsFromCache() {
    const selectedRuns = this.runSelector.getSelectedRuns();
    if (selectedRuns.size === 0) {
      this.showInitialState();
      return;
    }

    const metricsData = this.dataService.getCachedMetrics(selectedRuns);

    if (!this.clearAndRenderCharts(metricsData)) {
      this._setPageState('noData');
      this.hideChartControls();
      return;
    }

    this._setPageState('metrics');
    this.updateRunColorLegends();
  }

  initializeChart(chartId, metricName, runData) {
    const chart = new Chart(`#${chartId}`, {
      onZoomChange: (zoomState) => {
        if (this.syncZoom) {
          this.globalZoomState = zoomState;
          this.syncZoomToAllCharts(metricName);
        }
      },
    });

    const chartData = convertToChartFormat(metricName, runData);
    chartData.title = metricName;

    chart.setData(chartData);

    if (this.syncZoom && this.globalZoomState) {
      chart.setExternalZoom(this.globalZoomState);
    }

    return chart;
  }

  syncZoomToAllCharts(excludeMetricName) {
    for (const [metricName, chart] of this.charts.entries()) {
      if (metricName !== excludeMetricName && chart.setExternalZoom) {
        chart.setExternalZoom(this.globalZoomState);
      }
    }
  }

  showErrorState(message) {
    this._setPageState('noData');

    const errorElement = this.noDataState.querySelector('p');
    if (errorElement) {
      errorElement.textContent = `Error: ${message}`;
    }
  }

  updateRunColorLegends() {
    const firstChart = this.charts.values().next().value;
    if (!firstChart || !firstChart.getRunStyle) {
      this.runSelector.hideAllLegends();
      return;
    }

    this.runSelector.updateRunColorLegends((runName) => firstChart.getRunStyle(runName));
  }

  handleStatusUpdate(statusData) {
    updateRunStatusIcon(statusData, '[SSE]');
  }

  /**
   * Clean up all resources held by this page.
   * Overrides BaseChartPage.destroy() to also clean up project-specific
   * resources (dataService, runSelector, sseIndicator, event listeners).
   */
  destroy() {
    // Invalidate any in-flight showMetrics() request so its post-await
    // rendering/SSE setup is skipped after we tear down resources below.
    this._metricsRequestId++;

    // Clean up project-specific event listeners
    if (this.syncZoomCheckbox && this.syncZoomHandler) {
      this.syncZoomCheckbox.removeEventListener('change', this.syncZoomHandler);
      this.syncZoomHandler = null;
    }
    if (this.toggleSidebarBtn && this.sidebarToggleHandler) {
      this.toggleSidebarBtn.removeEventListener('click', this.sidebarToggleHandler);
      this.sidebarToggleHandler = null;
    }

    // Destroy owned child instances
    if (this.dataService) {
      this.dataService.destroy();
      this.dataService = null;
    }
    if (this.runSelector) {
      this.runSelector.destroy();
      this.runSelector = null;
    }
    if (this.noteEditor?.destroy) {
      this.noteEditor.destroy();
    }
    this.noteEditor = null;
    // SSEStatusIndicator holds no event listeners or async resources,
    // but null the reference for completeness.
    this.sseIndicator = null;

    // Destroy charts (delegates to Chart.destroy() for each)
    for (const chart of this.charts.values()) {
      if (chart.destroy) {
        chart.destroy();
      }
    }

    // Call parent cleanup (resize handlers, size buttons, charts map)
    super.destroy();
  }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  const page = new ProjectDetail();
  // Store for SPA cleanup
  window.__asparaPage = page;
  registerPageLifecycle(page);
});

export { ProjectDetail };
