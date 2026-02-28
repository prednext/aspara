/**
 * Unit tests for RunsListSorter
 */

import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

// Mock dependencies before import
vi.mock('../../src/aspara/dashboard/static/js/api/delete-api.js', () => ({
  deleteRunApi: vi.fn(),
}));
vi.mock('../../src/aspara/dashboard/static/js/tag-editor.js', () => ({
  initializeTagEditorsForElements: vi.fn(),
}));
vi.mock('../../src/aspara/dashboard/static/js/runs-list/utils.js', () => ({
  createRunSortComparator: vi.fn(() => () => 0),
  parseRunElement: vi.fn((el) => ({
    name: el.dataset.run,
    element: el,
    status: el.dataset.status || 'completed',
  })),
}));

import { deleteRunApi } from '../../src/aspara/dashboard/static/js/api/delete-api.js';
import { RunsListSorter } from '../../src/aspara/dashboard/static/js/runs-list/index.js';

function createRunsDOM(runCount = 2) {
  const cards = Array.from({ length: runCount }, (_, i) => {
    const name = `run-${i}`;
    return `<div class="run-card" data-run="${name}" data-project="proj" data-status="completed" tabindex="0">
      <div id="run-tags-${name}" data-project-name="proj" data-run-name="${name}"></div>
    </div>`;
  }).join('');

  document.body.innerHTML = `
    <div data-sort="name"><span class="sort-indicator">↕</span></div>
    <div data-sort="status"><span class="sort-indicator">↕</span></div>
    <div id="runs-container">${cards}</div>
  `;
}

describe('RunsListSorter', () => {
  let sorter;

  beforeEach(() => {
    document.body.innerHTML = '';
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    sorter = null;
  });

  describe('constructor', () => {
    test('should initialize with default sort settings', () => {
      createRunsDOM();
      sorter = new RunsListSorter();

      expect(sorter.sortKey).toBe('name');
      expect(sorter.sortOrder).toBe('asc');
    });

    test('should restore sort settings from localStorage', () => {
      localStorage.setItem('runs_sort_key', 'status');
      localStorage.setItem('runs_sort_order', 'desc');
      createRunsDOM();
      sorter = new RunsListSorter();

      expect(sorter.sortKey).toBe('status');
      expect(sorter.sortOrder).toBe('desc');
    });
  });

  describe('sort toggling', () => {
    test('should toggle sort order on same key click', () => {
      createRunsDOM();
      sorter = new RunsListSorter();

      document.querySelector('[data-sort="name"]').click();
      expect(sorter.sortOrder).toBe('desc');

      document.querySelector('[data-sort="name"]').click();
      expect(sorter.sortOrder).toBe('asc');
    });

    test('should change sort key on different key click', () => {
      createRunsDOM();
      sorter = new RunsListSorter();

      document.querySelector('[data-sort="status"]').click();
      expect(sorter.sortKey).toBe('status');
      expect(sorter.sortOrder).toBe('asc');
    });
  });

  describe('updateSortIndicators', () => {
    test('should show ascending indicator for active sort', () => {
      createRunsDOM();
      sorter = new RunsListSorter();

      const activeIndicator = document.querySelector('[data-sort="name"] .sort-indicator');
      expect(activeIndicator.textContent).toBe('↑');
      expect(activeIndicator.classList.contains('text-text-primary')).toBe(true);
    });

    test('should show neutral indicator for inactive sort', () => {
      createRunsDOM();
      sorter = new RunsListSorter();

      const inactiveIndicator = document.querySelector('[data-sort="status"] .sort-indicator');
      expect(inactiveIndicator.textContent).toBe('↕');
      expect(inactiveIndicator.classList.contains('text-text-muted')).toBe(true);
    });

    test('should show descending indicator after toggle', () => {
      createRunsDOM();
      sorter = new RunsListSorter();

      document.querySelector('[data-sort="name"]').click();
      const indicator = document.querySelector('[data-sort="name"] .sort-indicator');
      expect(indicator.textContent).toBe('↓');
    });
  });

  describe('sortAndRender', () => {
    test('should reorder elements in container', () => {
      createRunsDOM(3);
      sorter = new RunsListSorter();

      const container = document.getElementById('runs-container');
      expect(container.children.length).toBe(3);
    });

    test('should handle missing container', () => {
      createRunsDOM();
      sorter = new RunsListSorter();

      document.getElementById('runs-container').remove();
      expect(() => sorter.sortAndRender()).not.toThrow();
    });
  });

  describe('card navigation', () => {
    test('should navigate on card click', () => {
      createRunsDOM();
      sorter = new RunsListSorter();

      window.location = undefined;
      window.location = { href: '' };

      const card = document.querySelector('.run-card');
      card.click();

      expect(window.location.href).toContain('/projects/proj/runs/run-0');
    });

    test('should navigate on Enter key', () => {
      createRunsDOM();
      sorter = new RunsListSorter();

      window.location = undefined;
      window.location = { href: '' };

      const card = document.querySelector('.run-card');
      card.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));

      expect(window.location.href).toContain('/projects/proj/runs/run-0');
    });

    test('should not navigate when clicking tag editor', () => {
      createRunsDOM();
      sorter = new RunsListSorter();

      window.location = undefined;
      window.location = { href: '' };

      const card = document.querySelector('.run-card');
      const tagWrapper = document.createElement('div');
      tagWrapper.className = 'tag-editor-wrapper';
      card.appendChild(tagWrapper);

      const event = new MouseEvent('click', { bubbles: true });
      tagWrapper.dispatchEvent(event);

      expect(window.location.href).toBe('');
    });
  });

  describe('delete handlers', () => {
    test('should handle missing container', () => {
      document.body.innerHTML = `
        <div data-sort="name"><span class="sort-indicator">↕</span></div>
      `;
      expect(() => {
        sorter = new RunsListSorter();
      }).not.toThrow();
    });

    test('should handle delete button click', async () => {
      createRunsDOM();
      sorter = new RunsListSorter();
      window.showConfirm = vi.fn().mockResolvedValue(false);

      const container = document.getElementById('runs-container');
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'delete-run-btn';
      deleteBtn.dataset.project = 'proj';
      deleteBtn.dataset.run = 'run-0';
      container.querySelector('.run-card').appendChild(deleteBtn);

      deleteBtn.click();
      // Wait for async handler
      await vi.waitFor(() => {
        expect(window.showConfirm).toHaveBeenCalled();
      });
    });

    test('should ignore click without delete button', () => {
      createRunsDOM();
      sorter = new RunsListSorter();
      const handleSpy = vi.spyOn(sorter, 'handleDeleteRun');

      const container = document.getElementById('runs-container');
      container.dispatchEvent(new MouseEvent('click', { bubbles: true }));

      expect(handleSpy).not.toHaveBeenCalled();
    });

    test('should ignore delete button without project name', async () => {
      createRunsDOM();
      sorter = new RunsListSorter();

      const container = document.getElementById('runs-container');
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'delete-run-btn';
      // No project/run data attributes
      container.querySelector('.run-card').appendChild(deleteBtn);

      const handleSpy = vi.spyOn(sorter, 'handleDeleteRun');
      deleteBtn.click();

      // Should not call handleDeleteRun since projectName is falsy
      expect(handleSpy).not.toHaveBeenCalled();
    });
  });

  describe('handleDeleteRun', () => {
    test('should show error when names are missing', async () => {
      createRunsDOM();
      sorter = new RunsListSorter();
      window.showErrorNotification = vi.fn();

      await sorter.handleDeleteRun('', '');

      expect(window.showErrorNotification).toHaveBeenCalled();
    });

    test('should do nothing when not confirmed', async () => {
      createRunsDOM();
      sorter = new RunsListSorter();
      window.showConfirm = vi.fn().mockResolvedValue(false);

      await sorter.handleDeleteRun('proj', 'run-0');

      expect(deleteRunApi).not.toHaveBeenCalled();
    });

    test('should call deleteRunApi on confirm', async () => {
      vi.useFakeTimers();
      createRunsDOM();
      sorter = new RunsListSorter();
      window.showConfirm = vi.fn().mockResolvedValue(true);
      window.showSuccessNotification = vi.fn();
      window.location = { reload: vi.fn() };
      deleteRunApi.mockResolvedValue({ message: 'Deleted' });

      await sorter.handleDeleteRun('proj', 'run-0');

      expect(deleteRunApi).toHaveBeenCalledWith('proj', 'run-0');
      expect(window.showSuccessNotification).toHaveBeenCalled();
      vi.useRealTimers();
    });

    test('should show error on delete failure', async () => {
      createRunsDOM();
      sorter = new RunsListSorter();
      window.showConfirm = vi.fn().mockResolvedValue(true);
      window.showErrorNotification = vi.fn();
      deleteRunApi.mockRejectedValue(new Error('Network error'));

      await sorter.handleDeleteRun('proj', 'run-0');

      expect(window.showErrorNotification).toHaveBeenCalledWith(expect.stringContaining('Network error'));
    });
  });
});
