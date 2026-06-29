/**
 * Run selector component.
 * Handles run selection, filtering, and sorting UI in the project detail page.
 */

import { debounce } from '../timer-utils.js';

/**
 * RunSelector manages the run selection UI including checkboxes, filtering, and sorting.
 */
export class RunSelector {
  /**
   * @param {Object} options - Configuration options
   * @param {function} options.onSelectionChange - Callback when selection changes
   */
  constructor(options = {}) {
    this.selectedRuns = new Set();
    this.manuallyDeselectedRuns = new Set();
    this.allRuns = [];
    this.sortKey = localStorage.getItem('project_runs_sort_key') || 'name';
    this.sortOrder = localStorage.getItem('project_runs_sort_order') || 'asc';
    this.onSelectionChange = options.onSelectionChange || null;
    this.initialLoadComplete = false;

    // Stored handlers for cleanup
    this._filterHandler = null;
    this._filterDebounced = null;
    this._checkboxHandlers = [];
    this._sortButtonHandlers = [];

    this.initializeElements();
    this.setupEventListeners();
    this.loadInitialRuns();
  }

  /**
   * Initialize DOM element references.
   */
  initializeElements() {
    this.filterInput = document.getElementById('runFilter');
    this.selectedCountSpan = document.getElementById('selectedCount');
    this.runCheckboxes = document.querySelectorAll('.run-checkbox');
    this.collapsedSelectedCount = document.getElementById('collapsed-selected-count');
  }

  /**
   * Setup event listeners for run selection UI.
   */
  setupEventListeners() {
    if (this.filterInput) {
      // Debounce filter re-rendering to avoid reflowing the entire run list
      // on every keystroke (important for large run lists). Shares the
      // common debounce timing via timer-utils (SSOT).
      this._filterDebounced = debounce((value) => this.filterRuns(value));
      this._filterHandler = (e) => {
        this._filterDebounced(e.target.value);
      };
      this.filterInput.addEventListener('input', this._filterHandler);
    }

    for (const checkbox of this.runCheckboxes) {
      const handler = (e) => {
        this.handleRunSelection(e.target);
      };
      checkbox.addEventListener('change', handler);
      this._checkboxHandlers.push({ element: checkbox, handler });
    }

    const sortButtons = document.querySelectorAll('[data-sort-runs]');
    for (const button of sortButtons) {
      const handler = () => {
        const key = button.dataset.sortRuns;
        if (this.sortKey === key) {
          this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
        } else {
          this.sortKey = key;
          this.sortOrder = 'asc';
        }
        localStorage.setItem('project_runs_sort_key', this.sortKey);
        localStorage.setItem('project_runs_sort_order', this.sortOrder);
        this.updateSortIndicators();
        this.sortRuns();
      };
      button.addEventListener('click', handler);
      this._sortButtonHandlers.push({ element: button, handler });
    }

    this.updateSortIndicators();
  }

  /**
   * Load initial runs from checkboxes.
   */
  loadInitialRuns() {
    for (const checkbox of this.runCheckboxes) {
      const runName = checkbox.dataset.runName;
      this.allRuns.push(runName);
      this.selectedRuns.add(runName);
      checkbox.checked = true;
    }

    this.updateSelectedCount();
    this.sortRuns();
    this.initialLoadComplete = true;
  }

  /**
   * Update sort indicators in UI.
   */
  updateSortIndicators() {
    const sortButtons = document.querySelectorAll('[data-sort-runs]');
    for (const button of sortButtons) {
      const indicator = button.querySelector('.sort-runs-indicator');
      if (!indicator) continue;

      if (button.dataset.sortRuns === this.sortKey) {
        indicator.textContent = this.sortOrder === 'asc' ? '↑' : '↓';
        indicator.classList.remove('text-text-muted');
        indicator.classList.add('text-text-primary');
      } else {
        indicator.textContent = '↕';
        indicator.classList.remove('text-text-primary');
        indicator.classList.add('text-text-muted');
      }
    }
  }

  /**
   * Sort runs in the UI.
   */
  sortRuns() {
    const container = document.getElementById('runs-list-container');
    if (!container) return;

    const runItems = Array.from(container.querySelectorAll('.run-item'));

    runItems.sort((a, b) => {
      let aVal;
      let bVal;

      switch (this.sortKey) {
        case 'name':
          aVal = a.dataset.runName.toLowerCase();
          bVal = b.dataset.runName.toLowerCase();
          break;
        case 'lastUpdate':
          aVal = Number.parseInt(a.dataset.runLastUpdate) || 0;
          bVal = Number.parseInt(b.dataset.runLastUpdate) || 0;
          break;
        default:
          return 0;
      }

      if (aVal < bVal) return this.sortOrder === 'asc' ? -1 : 1;
      if (aVal > bVal) return this.sortOrder === 'asc' ? 1 : -1;
      return 0;
    });

    for (const item of runItems) {
      container.appendChild(item);
    }
  }

  /**
   * Filter runs by regex pattern.
   * @param {string} pattern - Regex pattern to filter runs
   */
  filterRuns(pattern) {
    const input = this.filterInput;

    try {
      const regex = new RegExp(pattern, 'i');

      // Valid regex - remove error state
      input?.classList.remove('border-status-error');

      for (const checkbox of this.runCheckboxes) {
        const runName = checkbox.dataset.runName;
        const runItem = checkbox.closest('.run-item');

        if (!pattern || regex.test(runName)) {
          runItem.style.display = '';
          if (pattern) {
            if (!this.manuallyDeselectedRuns.has(runName)) {
              checkbox.checked = true;
              this.selectedRuns.add(runName);
            }
          } else {
            if (!this.manuallyDeselectedRuns.has(runName)) {
              checkbox.checked = true;
              this.selectedRuns.add(runName);
            }
          }
        } else {
          runItem.style.display = 'none';
        }
      }

      this.updateSelectedCount();
    } catch (e) {
      // Invalid regex - add error state and show all runs
      input?.classList.add('border-status-error');

      for (const checkbox of this.runCheckboxes) {
        const runItem = checkbox.closest('.run-item');
        runItem.style.display = '';
      }
    }
  }

  /**
   * Handle checkbox change event.
   * @param {HTMLInputElement} checkbox - The changed checkbox element
   */
  handleRunSelection(checkbox) {
    const runName = checkbox.dataset.runName;

    if (checkbox.checked) {
      this.selectedRuns.add(runName);
      this.manuallyDeselectedRuns.delete(runName);
    } else {
      this.selectedRuns.delete(runName);
      this.manuallyDeselectedRuns.add(runName);
    }

    this.updateSelectedCount();

    if (this.initialLoadComplete && this.onSelectionChange) {
      this.onSelectionChange(this.selectedRuns);
    }
  }

  /**
   * Update the selected count display.
   */
  updateSelectedCount() {
    if (this.selectedCountSpan) {
      this.selectedCountSpan.textContent = this.selectedRuns.size;
    }
    if (this.collapsedSelectedCount) {
      this.collapsedSelectedCount.textContent = this.selectedRuns.size;
    }
  }

  /**
   * Get the set of selected runs.
   * @returns {Set<string>}
   */
  getSelectedRuns() {
    return this.selectedRuns;
  }

  /**
   * Update run color legends in the sidebar.
   * @param {function} getRunStyle - Function to get style for a run
   */
  updateRunColorLegends(getRunStyle) {
    for (const runName of this.selectedRuns) {
      const legendElement = document.querySelector(`[data-run-legend="${runName}"]`);
      if (!legendElement) continue;

      const style = getRunStyle(runName);
      if (!style) continue;

      const lineElement = legendElement.querySelector('line');
      if (lineElement) {
        lineElement.setAttribute('stroke', style.borderColor);

        if (style.borderDash && style.borderDash.length > 0) {
          lineElement.setAttribute('stroke-dasharray', style.borderDash.join(' '));
        } else {
          lineElement.removeAttribute('stroke-dasharray');
        }
      }

      legendElement.style.display = 'block';
    }

    // Hide legends for unselected runs
    for (const checkbox of this.runCheckboxes) {
      const runName = checkbox.dataset.runName;
      if (!this.selectedRuns.has(runName)) {
        const legendElement = document.querySelector(`[data-run-legend="${runName}"]`);
        if (legendElement) {
          legendElement.style.display = 'none';
        }
      }
    }
  }

  /**
   * Hide all color legends.
   */
  hideAllLegends() {
    const allLegends = document.querySelectorAll('[data-run-legend]');
    for (const legend of allLegends) {
      legend.style.display = 'none';
    }
  }

  /**
   * Clean up event listeners.
   */
  destroy() {
    if (this._filterDebounced) {
      this._filterDebounced.cancel();
      this._filterDebounced = null;
    }
    if (this.filterInput && this._filterHandler) {
      this.filterInput.removeEventListener('input', this._filterHandler);
      this._filterHandler = null;
    }
    for (const { element, handler } of this._checkboxHandlers) {
      element.removeEventListener('change', handler);
    }
    this._checkboxHandlers = [];
    for (const { element, handler } of this._sortButtonHandlers) {
      element.removeEventListener('click', handler);
    }
    this._sortButtonHandlers = [];
  }
}
