/**
 * Unit tests for RunSelector regex filtering
 */

import { beforeEach, describe, expect, test, vi } from 'vitest';
import { RunSelector } from '../../src/aspara/dashboard/static/js/components/run-selector.js';

describe('RunSelector', () => {
  /**
   * Helper to create DOM structure for RunSelector
   */
  function setupRunSelectorDOM(runNames) {
    document.body.innerHTML = `
      <input type="text" id="runFilter" placeholder="Filter runs (regex supported)">
      <span id="selectedCount">0</span>
      <span id="collapsed-selected-count">0</span>
      <div id="runs-list-container">
        ${runNames
          .map(
            (name) => `
          <div class="run-item" data-run-name="${name}" data-run-last-update="1234567890">
            <input type="checkbox" class="run-checkbox" value="${name}" data-run-name="${name}" checked>
            <span>${name}</span>
          </div>
        `
          )
          .join('')}
      </div>
      <button data-sort-runs="name"><span>Name</span><span class="sort-runs-indicator">↕</span></button>
      <button data-sort-runs="lastUpdate"><span>Date</span><span class="sort-runs-indicator">↕</span></button>
    `;
  }

  /**
   * Helper to get run item by name
   */
  function getRunItem(name) {
    return document.querySelector(`.run-item[data-run-name="${name}"]`);
  }

  /**
   * Helper to check if run is visible
   */
  function isRunVisible(name) {
    const item = getRunItem(name);
    return item && item.style.display !== 'none';
  }

  beforeEach(() => {
    document.body.innerHTML = '';
    localStorage.clear();
  });

  describe('Regex Filtering', () => {
    test('should filter runs with valid regex pattern', () => {
      setupRunSelectorDOM(['test-run-1', 'test-run-2', 'experiment-1', 'experiment-2']);
      const selector = new RunSelector();

      // Filter with regex pattern that starts with "test"
      selector.filterRuns('^test');

      // Check visibility by name (order may change due to sorting)
      expect(isRunVisible('test-run-1')).toBe(true);
      expect(isRunVisible('test-run-2')).toBe(true);
      expect(isRunVisible('experiment-1')).toBe(false);
      expect(isRunVisible('experiment-2')).toBe(false);
    });

    test('should filter runs with regex pattern ending with number', () => {
      setupRunSelectorDOM(['train-v1', 'train-v2', 'eval-run', 'test-v10']);
      const selector = new RunSelector();

      // Filter with regex pattern that ends with version number
      selector.filterRuns('v[0-9]+$');

      expect(isRunVisible('train-v1')).toBe(true);
      expect(isRunVisible('train-v2')).toBe(true);
      expect(isRunVisible('eval-run')).toBe(false);
      expect(isRunVisible('test-v10')).toBe(true);
    });

    test('should filter runs with OR regex pattern', () => {
      setupRunSelectorDOM(['train-run', 'eval-run', 'test-run', 'debug-run']);
      const selector = new RunSelector();

      // Filter with OR pattern
      selector.filterRuns('train|eval');

      expect(isRunVisible('train-run')).toBe(true);
      expect(isRunVisible('eval-run')).toBe(true);
      expect(isRunVisible('test-run')).toBe(false);
      expect(isRunVisible('debug-run')).toBe(false);
    });

    test('should be case-insensitive', () => {
      setupRunSelectorDOM(['TEST-run', 'Test-Run', 'test-RUN', 'experiment']);
      const selector = new RunSelector();

      selector.filterRuns('test');

      expect(isRunVisible('TEST-run')).toBe(true);
      expect(isRunVisible('Test-Run')).toBe(true);
      expect(isRunVisible('test-RUN')).toBe(true);
      expect(isRunVisible('experiment')).toBe(false);
    });

    test('should show all runs when filter is empty', () => {
      setupRunSelectorDOM(['run-1', 'run-2', 'run-3']);
      const selector = new RunSelector();

      // First filter to hide some
      selector.filterRuns('^run-1$');
      expect(isRunVisible('run-2')).toBe(false);

      // Clear filter
      selector.filterRuns('');

      expect(isRunVisible('run-1')).toBe(true);
      expect(isRunVisible('run-2')).toBe(true);
      expect(isRunVisible('run-3')).toBe(true);
    });
  });

  describe('Invalid Regex Handling', () => {
    test('should add error class for invalid regex', () => {
      setupRunSelectorDOM(['run-1', 'run-2']);
      const selector = new RunSelector();
      const filterInput = document.getElementById('runFilter');

      // Enter invalid regex (unclosed bracket)
      selector.filterRuns('[');

      expect(filterInput.classList.contains('border-status-error')).toBe(true);
    });

    test('should show all runs when regex is invalid', () => {
      setupRunSelectorDOM(['run-1', 'run-2', 'run-3']);
      const selector = new RunSelector();

      // First filter to hide some
      selector.filterRuns('^run-1$');
      expect(isRunVisible('run-2')).toBe(false);

      // Enter invalid regex - all runs should be visible
      selector.filterRuns('[invalid');

      expect(isRunVisible('run-1')).toBe(true);
      expect(isRunVisible('run-2')).toBe(true);
      expect(isRunVisible('run-3')).toBe(true);
    });

    test('should remove error class when regex becomes valid', () => {
      setupRunSelectorDOM(['run-1', 'run-2']);
      const selector = new RunSelector();
      const filterInput = document.getElementById('runFilter');

      // Enter invalid regex
      selector.filterRuns('[');
      expect(filterInput.classList.contains('border-status-error')).toBe(true);

      // Fix the regex
      selector.filterRuns('[a-z]');
      expect(filterInput.classList.contains('border-status-error')).toBe(false);
    });

    test('should remove error class when filter is cleared', () => {
      setupRunSelectorDOM(['run-1', 'run-2']);
      const selector = new RunSelector();
      const filterInput = document.getElementById('runFilter');

      // Enter invalid regex
      selector.filterRuns('(unclosed');
      expect(filterInput.classList.contains('border-status-error')).toBe(true);

      // Clear the filter
      selector.filterRuns('');
      expect(filterInput.classList.contains('border-status-error')).toBe(false);
    });

    test('should handle various invalid regex patterns', () => {
      setupRunSelectorDOM(['run-1']);
      const selector = new RunSelector();
      const filterInput = document.getElementById('runFilter');

      const invalidPatterns = [
        '[', // unclosed bracket
        '(', // unclosed parenthesis
        '*', // nothing to repeat
        '+', // nothing to repeat
        '?', // nothing to repeat
        '\\', // trailing backslash
      ];

      for (const pattern of invalidPatterns) {
        selector.filterRuns(pattern);
        expect(filterInput.classList.contains('border-status-error')).toBe(true);
      }
    });
  });

  describe('Filter Input Event Handling', () => {
    test('should filter runs on input event', () => {
      setupRunSelectorDOM(['test-1', 'test-2', 'other']);
      const selector = new RunSelector();
      const filterInput = document.getElementById('runFilter');

      // Simulate user typing
      filterInput.value = '^test';
      filterInput.dispatchEvent(new Event('input'));

      expect(isRunVisible('test-1')).toBe(true);
      expect(isRunVisible('test-2')).toBe(true);
      expect(isRunVisible('other')).toBe(false);
    });

    test('should show error state on invalid input', () => {
      setupRunSelectorDOM(['run-1']);
      const selector = new RunSelector();
      const filterInput = document.getElementById('runFilter');

      // Simulate user typing invalid regex
      filterInput.value = '[';
      filterInput.dispatchEvent(new Event('input'));

      expect(filterInput.classList.contains('border-status-error')).toBe(true);
    });
  });
});
