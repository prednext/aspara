import { deleteRunApi } from '../api/delete-api.js';
import { initializeTagEditorsForElements } from '../tag-editor.js';
import { createRunSortComparator, parseRunElement } from './utils.js';

class RunsListSorter {
  constructor() {
    this.runs = [];
    this.sortKey = localStorage.getItem('runs_sort_key') || 'name';
    this.sortOrder = localStorage.getItem('runs_sort_order') || 'asc';
    this.init();
  }

  init() {
    this.loadRuns();
    this.attachEventListeners();
    this.updateSortIndicators();
    this.sortAndRender();
    this.initializeTagEditors();
    this.initializeCardNavigation();
    this.initializeDeleteHandlers();
  }

  /**
   * Initialize tag editors for all runs
   */
  initializeTagEditors() {
    initializeTagEditorsForElements('[id^="run-tags-"]', (container) => {
      const projectName = container.dataset.projectName;
      const runName = container.dataset.runName;
      if (!projectName || !runName) return null;
      return `/api/projects/${projectName}/runs/${runName}/metadata`;
    });
  }

  /**
   * Initialize card navigation with proper event handling
   * Prevents navigation when clicking on interactive elements like tag editors or buttons
   */
  initializeCardNavigation() {
    const runCards = document.querySelectorAll('.run-card');
    for (const card of runCards) {
      card.addEventListener('click', (e) => {
        // Check if click is on a button or inside tag editor
        const isButton = e.target.closest('button');
        const isTagEditor = e.target.closest('.tag-editor-wrapper');
        const isTagContainer = e.target.closest('[id^="run-tags-"]');

        // Only navigate if not clicking on interactive elements
        if (!isButton && !isTagEditor && !isTagContainer) {
          this.navigateToRun(card);
        }
      });

      // Keyboard navigation: Enter or Space to activate
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          this.navigateToRun(card);
        }
      });
    }
  }

  /**
   * Navigate to run detail page
   * @param {HTMLElement} card - The run card element
   */
  navigateToRun(card) {
    const project = card.dataset.project;
    const run = card.dataset.run;
    window.location.href = `/projects/${encodeURIComponent(project)}/runs/${encodeURIComponent(run)}`;
  }

  loadRuns() {
    const runElements = document.querySelectorAll('.run-card[data-run]');
    this.runs = Array.from(runElements).map(parseRunElement);
  }

  attachEventListeners() {
    const headers = document.querySelectorAll('[data-sort]');
    for (const header of headers) {
      header.addEventListener('click', () => {
        const key = header.dataset.sort;
        if (this.sortKey === key) {
          this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
        } else {
          this.sortKey = key;
          this.sortOrder = 'asc';
        }
        localStorage.setItem('runs_sort_key', this.sortKey);
        localStorage.setItem('runs_sort_order', this.sortOrder);
        this.updateSortIndicators();
        this.sortAndRender();
      });
    }
  }

  updateSortIndicators() {
    const headers = document.querySelectorAll('[data-sort]');
    for (const header of headers) {
      const indicator = header.querySelector('.sort-indicator');
      if (header.dataset.sort === this.sortKey) {
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

  sortAndRender() {
    this.runs.sort(createRunSortComparator(this.sortKey, this.sortOrder));

    const container = document.getElementById('runs-container');
    if (container) {
      for (const run of this.runs) {
        container.appendChild(run.element);
      }
    }
  }

  /**
   * Initialize delete button handlers using event delegation
   */
  initializeDeleteHandlers() {
    const container = document.getElementById('runs-container');
    if (!container) return;

    container.addEventListener('click', async (e) => {
      const deleteBtn = e.target.closest('.delete-run-btn');
      if (!deleteBtn) return;

      e.stopPropagation();
      const projectName = deleteBtn.dataset.project;
      const runName = deleteBtn.dataset.run;
      if (!projectName || !runName) return;

      await this.handleDeleteRun(projectName, runName);
    });
  }

  /**
   * Handle run deletion with confirmation and notification
   * @param {string} projectName - The project name
   * @param {string} runName - The run name to delete
   */
  async handleDeleteRun(projectName, runName) {
    if (!projectName || !runName) {
      window.showErrorNotification?.('Project name or run name is not specified');
      return;
    }

    const confirmed = await window.showConfirm({
      title: 'Delete Run',
      message: `Are you sure you want to delete run "${runName}"?\nThis action cannot be undone.`,
      confirmText: 'Delete',
      variant: 'danger',
      dangerousAction: true,
    });
    if (!confirmed) return;

    try {
      const data = await deleteRunApi(projectName, runName);
      window.showSuccessNotification?.(data.message || 'Run has been deleted');
      setTimeout(() => window.location.reload(), 1000);
    } catch (error) {
      console.error('Error deleting run:', error);
      window.showErrorNotification?.(`Failed to delete: ${error.message}`);
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('runs-container')) {
    new RunsListSorter();
  }
});
