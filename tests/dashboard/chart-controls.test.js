/**
 * Unit tests for ChartControls (help popover, fullscreen title, download menu).
 */
import { afterEach, beforeEach, describe, expect, test } from 'vitest';
import { ChartControls } from '../../src/aspara/dashboard/static/js/chart/controls.js';

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
});
