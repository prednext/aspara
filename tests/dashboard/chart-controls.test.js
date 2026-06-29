/**
 * Unit tests for ChartControls (help popover, fullscreen title, download menu).
 */
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { ChartControls } from '../../src/aspara/dashboard/static/js/chart/controls.js';
import { CHART_CONTROL_LABELS } from '../../src/aspara/dashboard/static/js/html-utils.js';

function createMockChart() {
  const container = document.createElement('div');
  document.body.appendChild(container);
  return {
    container,
    resetZoom: () => {},
  };
}

function createMockExport() {
  return { downloadData: () => {} };
}

describe('ChartControls', () => {
  let controls;
  let chart;

  beforeEach(() => {
    chart = createMockChart();
    controls = new ChartControls(chart, createMockExport());
    controls.create();
  });

  afterEach(() => {
    controls.destroy();
    chart.container.remove();
  });

  describe('fullscreen button title', () => {
    test('starts with "Enter fullscreen" instead of "Fit to full size"', () => {
      expect(controls.fullSizeButton.title).toBe('Enter fullscreen');
    });

    test('fitToFullSize toggles title to "Exit fullscreen" when entering', () => {
      // requestFullscreen is not implemented in jsdom; stub it so the
      // non-fullscreen branch runs.
      chart.container.requestFullscreen = () => {};
      controls.fitToFullSize();
      expect(controls.fullSizeButton.title).toBe('Exit fullscreen');
    });

    test('fullscreenchange event syncs title back to "Enter fullscreen"', () => {
      chart.container.requestFullscreen = () => {};
      controls.fitToFullSize();
      expect(controls.fullSizeButton.title).toBe('Exit fullscreen');

      // Simulate browser exiting fullscreen (e.g. via Esc).
      document.dispatchEvent(new Event('fullscreenchange'));
      expect(controls.fullSizeButton.title).toBe('Enter fullscreen');
    });
  });

  describe('help button', () => {
    test('creates a help button with the help icon', () => {
      expect(controls.helpButton).toBeTruthy();
      expect(controls.helpButton.title).toBe('Chart interactions help');
    });

    test('popover is hidden by default', () => {
      expect(controls.helpPopover.style.display).toBe('none');
    });

    test('clicking the help button toggles the popover', () => {
      controls.helpButton.click();
      expect(controls.helpPopover.style.display).toBe('flex');

      controls.helpButton.click();
      expect(controls.helpPopover.style.display).toBe('none');
    });

    test('popover lists all four chart interactions', () => {
      const rows = controls.helpPopover.querySelectorAll('div');
      const texts = Array.from(rows).map((r) => r.textContent.trim());
      expect(texts.some((t) => t.includes('Drag on chart to zoom'))).toBe(true);
      expect(texts.some((t) => t.includes('Click reset to restore view'))).toBe(true);
      expect(texts.some((t) => t.includes('Click fullscreen to expand'))).toBe(true);
      expect(texts.some((t) => t.includes('Click download to export data'))).toBe(true);
    });

    test('clicking outside the help button closes the popover', () => {
      controls.helpButton.click();
      expect(controls.helpPopover.style.display).toBe('flex');

      document.body.click();
      expect(controls.helpPopover.style.display).toBe('none');
    });
  });

  describe('destroy', () => {
    test('removes the fullscreenchange listener', () => {
      const spy = vi.spyOn(document, 'removeEventListener');
      controls.destroy();
      // fullscreenchange listener should have been removed
      const removed = spy.mock.calls.some(
        ([event]) => event === 'fullscreenchange'
      );
      expect(removed).toBe(true);
      spy.mockRestore();
    });

    test('nulls out help button and popover references', () => {
      controls.destroy();
      expect(controls.helpButton).toBeNull();
      expect(controls.helpPopover).toBeNull();
    });
  });

  describe('accessibility', () => {
    test('every control button has an aria-label matching its title', () => {
      for (const btn of [controls.resetButton, controls.fullSizeButton, controls.downloadButton, controls.helpButton]) {
        expect(btn.getAttribute('aria-label')).toBe(btn.title);
        expect(btn.getAttribute('aria-label')).not.toBe('');
      }
    });

    test('reset button aria-label is the SSOT label', () => {
      expect(controls.resetButton.getAttribute('aria-label')).toBe(CHART_CONTROL_LABELS.resetZoom);
    });

    test('download button declares aria-haspopup=menu and aria-expanded', () => {
      expect(controls.downloadButton.getAttribute('aria-haspopup')).toBe('menu');
      expect(controls.downloadButton.getAttribute('aria-expanded')).toBe('false');
    });

    test('help button declares aria-haspopup=dialog and aria-expanded', () => {
      expect(controls.helpButton.getAttribute('aria-haspopup')).toBe('dialog');
      expect(controls.helpButton.getAttribute('aria-expanded')).toBe('false');
    });

    test('download menu has role=menu and items have role=menuitem', () => {
      expect(controls.downloadMenu.getAttribute('role')).toBe('menu');
      const items = controls.downloadMenu.querySelectorAll('[role="menuitem"]');
      expect(items.length).toBe(3);
    });

    test('opening download menu sets aria-expanded=true and focuses first item', () => {
      controls.toggleDownloadMenu(true);
      expect(controls.downloadButton.getAttribute('aria-expanded')).toBe('true');
      const firstItem = controls.downloadMenu.querySelector('[role="menuitem"]');
      expect(document.activeElement).toBe(firstItem);
    });

    test('closing download menu sets aria-expanded=false', () => {
      controls.toggleDownloadMenu(true);
      controls.toggleDownloadMenu(false);
      expect(controls.downloadButton.getAttribute('aria-expanded')).toBe('false');
    });

    test('opening help popover sets aria-expanded=true', () => {
      controls.toggleHelpPopover(true);
      expect(controls.helpButton.getAttribute('aria-expanded')).toBe('true');
    });

    test('Esc closes the download menu and returns focus to the trigger', () => {
      controls.toggleDownloadMenu(true);
      const firstItem = controls.downloadMenu.querySelector('[role="menuitem"]');
      firstItem.focus();
      expect(controls.downloadMenu.style.display).toBe('flex');

      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));

      expect(controls.downloadMenu.style.display).toBe('none');
      expect(document.activeElement).toBe(controls.downloadButton);
    });

    test('Esc closes the help popover and returns focus to the trigger', () => {
      controls.toggleHelpPopover(true);
      expect(controls.helpPopover.style.display).toBe('flex');

      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));

      expect(controls.helpPopover.style.display).toBe('none');
      expect(document.activeElement).toBe(controls.helpButton);
    });

    test('ArrowDown wraps to the first download menu item from the last', () => {
      controls.toggleDownloadMenu(true);
      const items = controls.downloadMenu.querySelectorAll('[role="menuitem"]');
      items[items.length - 1].focus();

      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown' }));

      expect(document.activeElement).toBe(items[0]);
    });

    test('ArrowUp wraps to the last download menu item from the first', () => {
      controls.toggleDownloadMenu(true);
      const items = controls.downloadMenu.querySelectorAll('[role="menuitem"]');
      items[0].focus();

      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp' }));

      expect(document.activeElement).toBe(items[items.length - 1]);
    });

    test('Home focuses the first download menu item', () => {
      controls.toggleDownloadMenu(true);
      const items = controls.downloadMenu.querySelectorAll('[role="menuitem"]');
      items[1].focus();

      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Home' }));

      expect(document.activeElement).toBe(items[0]);
    });

    test('End focuses the last download menu item', () => {
      controls.toggleDownloadMenu(true);
      const items = controls.downloadMenu.querySelectorAll('[role="menuitem"]');
      items[0].focus();

      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'End' }));

      expect(document.activeElement).toBe(items[items.length - 1]);
    });

    test('Esc does nothing when no popup is open', () => {
      // Ensure both popups are closed.
      controls.toggleDownloadMenu(false);
      controls.toggleHelpPopover(false);
      // Dispatching Esc must not throw and must not change focus.
      const before = document.activeElement;
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      expect(document.activeElement).toBe(before);
    });

    test('fullscreenchange syncs aria-label alongside title', () => {
      chart.container.requestFullscreen = () => {};
      controls.fitToFullSize();
      expect(controls.fullSizeButton.getAttribute('aria-label')).toBe(CHART_CONTROL_LABELS.exitFullscreen);

      // Simulate browser exiting fullscreen (e.g. via Esc).
      document.dispatchEvent(new Event('fullscreenchange'));
      expect(controls.fullSizeButton.getAttribute('aria-label')).toBe(CHART_CONTROL_LABELS.enterFullscreen);
    });

    test('destroy removes the keydown listener', () => {
      const spy = vi.spyOn(document, 'removeEventListener');
      controls.destroy();
      const removed = spy.mock.calls.some(([event]) => event === 'keydown');
      expect(removed).toBe(true);
      spy.mockRestore();
    });
  });
});
