/**
 * Unit tests for ProjectsListSorter
 */

import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

// Mock dependencies before import
vi.mock('../../src/aspara/dashboard/static/js/api/delete-api.js', () => ({
  deleteProjectApi: vi.fn(),
}));
vi.mock('../../src/aspara/dashboard/static/js/projects-list-utils.js', () => ({
  createSortComparator: vi.fn(() => () => 0),
  matchesSearch: vi.fn(() => true),
  parseProjectElement: vi.fn((el) => ({
    name: el.dataset.project,
    element: el,
    runCount: Number.parseInt(el.dataset.runCount || '0', 10),
    latestRun: el.dataset.latestRun || '',
  })),
}));
vi.mock('../../src/aspara/dashboard/static/js/tag-editor.js', () => ({
  initializeTagEditorsForElements: vi.fn(),
}));

import { deleteProjectApi } from '../../src/aspara/dashboard/static/js/api/delete-api.js';
import { matchesSearch } from '../../src/aspara/dashboard/static/js/projects-list-utils.js';
import { ProjectsListSorter } from '../../src/aspara/dashboard/static/js/projects-list.js';

function createProjectsDOM({ searchMode = 'realtime', projectCount = 2 } = {}) {
  const cards = Array.from({ length: projectCount }, (_, i) => {
    const name = `project-${i}`;
    return `<div class="project-card" data-project="${name}" data-run-count="${i + 1}" data-latest-run="2026-01-01">
      <div id="project-tags-${name}" data-project-name="${name}"></div>
    </div>`;
  }).join('');

  document.body.innerHTML = `
    <div id="projects-root" data-search-mode="${searchMode}">
      <input id="projectSearchInput" type="text" />
      <button id="projectSearchButton">Search</button>
      <div data-sort="name"><span class="sort-indicator">↕</span></div>
      <div data-sort="runCount"><span class="sort-indicator">↕</span></div>
      <div id="projects-container">${cards}</div>
    </div>
  `;
}

describe('ProjectsListSorter', () => {
  let sorter;

  beforeEach(() => {
    document.body.innerHTML = '';
    localStorage.clear();
    vi.clearAllMocks();
    matchesSearch.mockReturnValue(true);
  });

  afterEach(() => {
    if (sorter) {
      sorter.destroy();
      sorter = null;
    }
  });

  describe('constructor', () => {
    test('should initialize with default sort settings', () => {
      createProjectsDOM();
      sorter = new ProjectsListSorter();

      expect(sorter.sortKey).toBe('name');
      expect(sorter.sortOrder).toBe('asc');
      expect(sorter.currentQuery).toBe('');
    });

    test('should restore sort settings from localStorage', () => {
      localStorage.setItem('projects_sort_key', 'runCount');
      localStorage.setItem('projects_sort_order', 'desc');
      createProjectsDOM();
      sorter = new ProjectsListSorter();

      expect(sorter.sortKey).toBe('runCount');
      expect(sorter.sortOrder).toBe('desc');
    });
  });

  describe('sort toggling', () => {
    test('should toggle sort order on same key click', () => {
      createProjectsDOM();
      sorter = new ProjectsListSorter();

      const nameHeader = document.querySelector('[data-sort="name"]');
      nameHeader.click();

      expect(sorter.sortOrder).toBe('desc');
      expect(localStorage.getItem('projects_sort_order')).toBe('desc');
    });

    test('should change sort key and reset order on different key click', () => {
      createProjectsDOM();
      sorter = new ProjectsListSorter();

      const countHeader = document.querySelector('[data-sort="runCount"]');
      countHeader.click();

      expect(sorter.sortKey).toBe('runCount');
      expect(sorter.sortOrder).toBe('asc');
    });
  });

  describe('updateSortIndicators', () => {
    test('should show correct indicators for active sort', () => {
      createProjectsDOM();
      sorter = new ProjectsListSorter();

      const nameIndicator = document.querySelector('[data-sort="name"] .sort-indicator');
      const countIndicator = document.querySelector('[data-sort="runCount"] .sort-indicator');

      expect(nameIndicator.textContent).toBe('↑');
      expect(nameIndicator.classList.contains('text-text-primary')).toBe(true);
      expect(countIndicator.textContent).toBe('↕');
      expect(countIndicator.classList.contains('text-text-muted')).toBe(true);
    });

    test('should update indicators on sort change', () => {
      createProjectsDOM();
      sorter = new ProjectsListSorter();

      // Click name again to change to desc
      document.querySelector('[data-sort="name"]').click();

      const nameIndicator = document.querySelector('[data-sort="name"] .sort-indicator');
      expect(nameIndicator.textContent).toBe('↓');
    });
  });

  describe('search - realtime mode', () => {
    test('should hide search button in realtime mode', () => {
      createProjectsDOM({ searchMode: 'realtime' });
      sorter = new ProjectsListSorter();

      const btn = document.getElementById('projectSearchButton');
      expect(btn.style.display).toBe('none');
    });

    test('should debounce search input', async () => {
      vi.useFakeTimers();
      createProjectsDOM({ searchMode: 'realtime' });
      sorter = new ProjectsListSorter();

      const input = document.getElementById('projectSearchInput');
      input.value = 'test';
      input.dispatchEvent(new Event('input'));

      expect(sorter.currentQuery).toBe('');

      vi.advanceTimersByTime(300);
      expect(sorter.currentQuery).toBe('test');

      vi.useRealTimers();
    });
  });

  describe('search - button mode', () => {
    test('should search on button click', () => {
      createProjectsDOM({ searchMode: 'button' });
      sorter = new ProjectsListSorter();

      const input = document.getElementById('projectSearchInput');
      const btn = document.getElementById('projectSearchButton');
      input.value = 'query';
      btn.click();

      expect(sorter.currentQuery).toBe('query');
    });

    test('should search on Enter key', () => {
      createProjectsDOM({ searchMode: 'button' });
      sorter = new ProjectsListSorter();

      const input = document.getElementById('projectSearchInput');
      input.value = 'enter-query';
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));

      expect(sorter.currentQuery).toBe('enter-query');
    });
  });

  describe('setupSearch', () => {
    test('should handle missing search input', () => {
      document.body.innerHTML = `
        <div id="projects-container">
          <div class="project-card" data-project="p1"></div>
        </div>
        <div data-sort="name"><span class="sort-indicator">↕</span></div>
      `;
      expect(() => {
        sorter = new ProjectsListSorter();
      }).not.toThrow();
    });
  });

  describe('sortAndRender', () => {
    test('should filter projects based on search', () => {
      createProjectsDOM({ projectCount: 3 });
      sorter = new ProjectsListSorter();

      // Only match first project
      matchesSearch.mockImplementation((project) => project.name === 'project-0');
      sorter.sortAndRender();

      const container = document.getElementById('projects-container');
      expect(container.children.length).toBe(1);
    });

    test('should handle missing container', () => {
      createProjectsDOM();
      sorter = new ProjectsListSorter();

      document.getElementById('projects-container').remove();
      expect(() => sorter.sortAndRender()).not.toThrow();
    });
  });

  describe('card navigation', () => {
    test('should navigate on card click', () => {
      createProjectsDOM();
      sorter = new ProjectsListSorter();

      // Mock location
      window.location = undefined;
      window.location = { href: '' };

      const card = document.querySelector('.project-card');
      card.click();

      expect(window.location.href).toContain('/projects/project-0');
    });

    test('should navigate on Enter key', () => {
      createProjectsDOM();
      sorter = new ProjectsListSorter();

      window.location = undefined;
      window.location = { href: '' };

      const card = document.querySelector('.project-card');
      card.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));

      expect(window.location.href).toContain('/projects/project-0');
    });

    test('should navigate on Space key', () => {
      createProjectsDOM();
      sorter = new ProjectsListSorter();

      window.location = undefined;
      window.location = { href: '' };

      const card = document.querySelector('.project-card');
      card.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));

      expect(window.location.href).toContain('/projects/project-0');
    });

    test('should not navigate when clicking button inside card', () => {
      createProjectsDOM();
      sorter = new ProjectsListSorter();

      window.location = undefined;
      window.location = { href: '' };

      const card = document.querySelector('.project-card');
      const button = document.createElement('button');
      card.appendChild(button);

      // Simulate click with target being the button
      const event = new MouseEvent('click', { bubbles: true });
      button.dispatchEvent(event);

      expect(window.location.href).toBe('');
    });
  });

  describe('delete handlers', () => {
    test('should handle missing container', () => {
      document.body.innerHTML = `
        <div data-sort="name"><span class="sort-indicator">↕</span></div>
      `;
      expect(() => {
        sorter = new ProjectsListSorter();
      }).not.toThrow();
    });

    test('should ignore clicks on non-delete buttons', () => {
      createProjectsDOM();
      sorter = new ProjectsListSorter();
      const handleSpy = vi.spyOn(sorter, 'handleDeleteProject');

      const container = document.getElementById('projects-container');
      container.dispatchEvent(new MouseEvent('click', { bubbles: true }));

      expect(handleSpy).not.toHaveBeenCalled();
    });
  });

  describe('handleDeleteProject', () => {
    test('should show error when projectName is empty', async () => {
      createProjectsDOM();
      sorter = new ProjectsListSorter();
      window.showErrorNotification = vi.fn();

      await sorter.handleDeleteProject('');

      expect(window.showErrorNotification).toHaveBeenCalled();
    });

    test('should do nothing when not confirmed', async () => {
      createProjectsDOM();
      sorter = new ProjectsListSorter();
      window.showConfirm = vi.fn().mockResolvedValue(false);

      await sorter.handleDeleteProject('project-0');

      expect(deleteProjectApi).not.toHaveBeenCalled();
    });

    test('should show error when project not found', async () => {
      createProjectsDOM();
      sorter = new ProjectsListSorter();
      window.showConfirm = vi.fn().mockResolvedValue(true);
      window.showErrorNotification = vi.fn();

      await sorter.handleDeleteProject('nonexistent');

      expect(window.showErrorNotification).toHaveBeenCalledWith('Project not found');
    });
  });

  describe('destroy', () => {
    test('should clean up timeout and handler', () => {
      vi.useFakeTimers();
      createProjectsDOM({ searchMode: 'realtime' });
      sorter = new ProjectsListSorter();

      // Trigger a search to set timeout
      const input = document.getElementById('projectSearchInput');
      input.value = 'x';
      input.dispatchEvent(new Event('input'));

      expect(sorter.searchTimeoutId).not.toBeNull();
      expect(sorter.searchInputHandler).not.toBeNull();

      sorter.destroy();

      expect(sorter.searchTimeoutId).toBeNull();
      expect(sorter.searchInputHandler).toBeNull();

      vi.useRealTimers();
    });

    test('should be safe to call without search input', () => {
      document.body.innerHTML = `
        <div id="projects-container">
          <div class="project-card" data-project="p1"></div>
        </div>
        <div data-sort="name"><span class="sort-indicator">↕</span></div>
      `;
      sorter = new ProjectsListSorter();
      expect(() => sorter.destroy()).not.toThrow();
    });
  });
});
