import { deleteProjectApi } from './api/delete-api.js';
import { createSortComparator, matchesSearch, parseProjectElement } from './projects-list-utils.js';
import { initializeTagEditorsForElements } from './tag-editor.js';

class ProjectsListSorter {
  constructor() {
    this.projects = [];
    this.currentQuery = '';
    this.searchMode = 'realtime';
    this.sortKey = localStorage.getItem('projects_sort_key') || 'name';
    this.sortOrder = localStorage.getItem('projects_sort_order') || 'asc';

    // Search input handler and timeout (stored for cleanup)
    this.searchInputHandler = null;
    this.searchTimeoutId = null;

    this.init();
  }

  init() {
    this.loadProjects();
    this.setupSearch();
    this.attachEventListeners();
    this.updateSortIndicators();
    this.sortAndRender();
    this.initializeTagEditors();
    this.initializeCardNavigation();
    this.initializeDeleteHandlers();
  }

  /**
   * Initialize tag editors for all projects
   */
  initializeTagEditors() {
    initializeTagEditorsForElements('[id^="project-tags-"]', (container) => {
      const projectName = container.dataset.projectName;
      if (!projectName) return null;
      return `/api/projects/${projectName}/metadata`;
    });
  }

  /**
   * Initialize card navigation with proper event handling
   * Prevents navigation when clicking on interactive elements like tag editors or buttons
   */
  initializeCardNavigation() {
    const projectCards = document.querySelectorAll('.project-card');
    for (const card of projectCards) {
      card.addEventListener('click', (e) => {
        // Check if click is on a button or inside tag editor
        const isButton = e.target.closest('button');
        const isTagEditor = e.target.closest('.tag-editor-wrapper');
        const isTagContainer = e.target.closest('[id^="project-tags-"]');

        // Only navigate if not clicking on interactive elements
        if (!isButton && !isTagEditor && !isTagContainer) {
          this.navigateToProject(card);
        }
      });

      // Keyboard navigation: Enter or Space to activate
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          this.navigateToProject(card);
        }
      });
    }
  }

  /**
   * Navigate to project detail page
   * @param {HTMLElement} card - The project card element
   */
  navigateToProject(card) {
    const project = card.dataset.project;
    window.location.href = `/projects/${encodeURIComponent(project)}`;
  }

  loadProjects() {
    const projectElements = document.querySelectorAll('.project-card[data-project]');
    this.projects = Array.from(projectElements).map(parseProjectElement);
  }

  setupSearch() {
    const root = document.getElementById('projects-root');
    if (root?.dataset.searchMode) {
      this.searchMode = root.dataset.searchMode;
    }

    const searchInput = document.getElementById('projectSearchInput');
    const searchButton = document.getElementById('projectSearchButton');

    if (!searchInput) {
      return;
    }

    if (this.searchMode === 'realtime') {
      if (searchButton) {
        searchButton.style.display = 'none';
      }

      // Store handler for cleanup
      this.searchInputHandler = (event) => {
        const value = event.target.value;
        if (this.searchTimeoutId) {
          clearTimeout(this.searchTimeoutId);
        }
        this.searchTimeoutId = setTimeout(() => {
          this.currentQuery = value.trim();
          this.sortAndRender();
        }, 300);
      };
      searchInput.addEventListener('input', this.searchInputHandler);
    } else {
      if (searchButton) {
        searchButton.addEventListener('click', () => {
          this.currentQuery = searchInput.value.trim();
          this.sortAndRender();
        });
      }

      searchInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          this.currentQuery = searchInput.value.trim();
          this.sortAndRender();
        }
      });
    }
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
        localStorage.setItem('projects_sort_key', this.sortKey);
        localStorage.setItem('projects_sort_order', this.sortOrder);
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
    this.projects.sort(createSortComparator(this.sortKey, this.sortOrder));

    const container = document.getElementById('projects-container');
    if (container) {
      for (const project of this.projects) {
        project.element.remove();
      }

      for (const project of this.projects) {
        if (matchesSearch(project, this.currentQuery)) {
          container.appendChild(project.element);
        }
      }
    }
  }

  /**
   * Initialize delete button handlers using event delegation
   */
  initializeDeleteHandlers() {
    const container = document.getElementById('projects-container');
    if (!container) return;

    container.addEventListener('click', async (e) => {
      const deleteBtn = e.target.closest('.delete-project-btn');
      if (!deleteBtn) return;

      e.stopPropagation();
      const projectName = deleteBtn.dataset.project;
      if (!projectName) return;

      await this.handleDeleteProject(projectName);
    });
  }

  /**
   * Handle project deletion with confirmation and notification
   * Uses optimistic UI: immediately removes card, restores on error
   * @param {string} projectName - The project name to delete
   */
  async handleDeleteProject(projectName) {
    if (!projectName) {
      window.showErrorNotification?.('Project name is not specified');
      return;
    }

    const confirmed = await window.showConfirm({
      title: 'Delete Project',
      message: `Are you sure you want to delete project "${projectName}"?\nThis action cannot be undone.`,
      confirmText: 'Delete',
      variant: 'danger',
      dangerousAction: true,
    });
    if (!confirmed) return;

    // Find the project and its card
    const projectIndex = this.projects.findIndex((p) => p.name === projectName);
    if (projectIndex === -1) {
      window.showErrorNotification?.('Project not found');
      return;
    }

    const project = this.projects[projectIndex];
    const card = project.element;
    const nextSibling = card.nextElementSibling;
    const parent = card.parentElement;

    // Save original styles for restoration
    const originalStyles = {
      height: card.offsetHeight,
      marginTop: card.style.marginTop,
      marginBottom: card.style.marginBottom,
      paddingTop: card.style.paddingTop,
      paddingBottom: card.style.paddingBottom,
      opacity: card.style.opacity,
      overflow: card.style.overflow,
      border: card.style.border,
      transition: card.style.transition,
    };

    // Remove from data array (optimistic)
    this.projects.splice(projectIndex, 1);

    // Animate card collapse
    await this.animateCardCollapse(card);

    try {
      await deleteProjectApi(projectName);
      // Success: remove card from DOM
      card.remove();
      window.showSuccessNotification?.('Project has been deleted');
    } catch (error) {
      console.error('Error deleting project:', error);

      // Restore to data array
      this.projects.splice(projectIndex, 0, project);

      // Restore card with highlight animation
      await this.restoreCard(card, nextSibling, parent, originalStyles);

      window.showErrorNotification?.(`Failed to delete project: ${error.message}`);
    }
  }

  /**
   * Wait for specified milliseconds
   * @param {number} ms - Milliseconds to wait
   * @returns {Promise<void>}
   */
  wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Animate card collapse (fade out + shrink)
   * @param {HTMLElement} card - The card element to collapse
   */
  async animateCardCollapse(card) {
    // Phase 1: Fade out
    card.style.transition = 'opacity 150ms ease-out';
    card.style.opacity = '0';
    await this.wait(150);

    // Phase 2: Collapse height
    card.style.overflow = 'hidden';
    card.style.transition =
      'height 200ms ease-out, margin-top 200ms ease-out, margin-bottom 200ms ease-out, padding-top 200ms ease-out, padding-bottom 200ms ease-out';
    card.style.height = `${card.offsetHeight}px`; // Set explicit height before animating
    card.style.border = 'none';

    // Force reflow
    card.offsetHeight;

    card.style.height = '0';
    card.style.marginTop = '0';
    card.style.marginBottom = '0';
    card.style.paddingTop = '0';
    card.style.paddingBottom = '0';

    await this.wait(200);
  }

  /**
   * Restore card with highlight animation
   * @param {HTMLElement} card - The card element to restore
   * @param {HTMLElement|null} nextSibling - The next sibling element
   * @param {HTMLElement} parent - The parent container
   * @param {Object} originalStyles - Original style values
   */
  async restoreCard(card, nextSibling, parent, originalStyles) {
    // Re-insert card in correct position if needed
    if (!card.parentElement) {
      if (nextSibling) {
        parent.insertBefore(card, nextSibling);
      } else {
        parent.appendChild(card);
      }
    }

    // Phase 1: Expand height
    card.style.transition =
      'height 200ms ease-out, margin-top 200ms ease-out, margin-bottom 200ms ease-out, padding-top 200ms ease-out, padding-bottom 200ms ease-out';
    card.style.height = `${originalStyles.height}px`;
    card.style.marginTop = originalStyles.marginTop || '';
    card.style.marginBottom = originalStyles.marginBottom || '';
    card.style.paddingTop = originalStyles.paddingTop || '';
    card.style.paddingBottom = originalStyles.paddingBottom || '';

    await this.wait(200);

    // Phase 2: Fade in with red highlight
    card.style.transition = 'opacity 200ms ease-out';
    card.style.opacity = '1';
    card.style.boxShadow = '0 0 0 2px rgba(239, 68, 68, 0.7)';

    await this.wait(200);

    // Phase 3: Fade out highlight
    card.style.transition = 'box-shadow 1000ms ease-out';
    card.style.boxShadow = '';

    await this.wait(1000);

    // Clean up styles
    card.style.height = '';
    card.style.overflow = originalStyles.overflow || '';
    card.style.border = originalStyles.border || '';
    card.style.transition = originalStyles.transition || '';
  }

  /**
   * Clean up event listeners and timeouts.
   */
  destroy() {
    if (this.searchTimeoutId) {
      clearTimeout(this.searchTimeoutId);
      this.searchTimeoutId = null;
    }
    if (this.searchInputHandler) {
      const searchInput = document.getElementById('projectSearchInput');
      if (searchInput) {
        searchInput.removeEventListener('input', this.searchInputHandler);
      }
      this.searchInputHandler = null;
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('projects-container')) {
    new ProjectsListSorter();
  }
});

export { ProjectsListSorter };
