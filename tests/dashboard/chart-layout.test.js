/**
 * Unit tests for chart layout utilities.
 */
import { beforeEach, describe, expect, test } from 'vitest';
import {
  applyGridLayout,
  calculateChartDimensions,
  updateChartHeights,
  updateContainerPadding,
  updateSizeButtonStyles,
} from '../../src/aspara/dashboard/static/js/metrics/chart-layout.js';

describe('calculateChartDimensions', () => {
  test('returns dimensions for medium size by default', () => {
    const result = calculateChartDimensions(1200, 'M');
    expect(result.columns).toBe(3);
    expect(result.gap).toBe(32);
    expect(result.padding).toBe(24);
    expect(result.chartWidth).toBeCloseTo(378.67, 1);
    expect(result.chartHeight).toBeGreaterThan(0);
  });

  test('returns more columns for small size', () => {
    const small = calculateChartDimensions(1200, 'S');
    const medium = calculateChartDimensions(1200, 'M');
    expect(small.columns).toBeGreaterThan(medium.columns);
  });

  test('returns fewer columns for large size', () => {
    const large = calculateChartDimensions(1200, 'L');
    const medium = calculateChartDimensions(1200, 'M');
    expect(large.columns).toBeLessThan(medium.columns);
  });
});

describe('applyGridLayout', () => {
  test('applies grid styles and removes space-y-8', () => {
    const container = document.createElement('div');
    container.className = 'space-y-8';
    applyGridLayout(container, 2, 32);
    expect(container.style.display).toBe('grid');
    expect(container.style.gridTemplateColumns).toBe('repeat(2, 1fr)');
    expect(container.style.gap).toBe('32px');
    expect(container.classList.contains('space-y-8')).toBe(false);
  });
});

describe('updateChartHeights', () => {
  let chartsContainer;

  beforeEach(() => {
    chartsContainer = document.createElement('div');
    // Simulate two metric chart containers with title and chart div
    for (const metricName of ['loss', 'accuracy']) {
      const chartContainer = document.createElement('div');
      chartContainer.className = 'bg-base-surface border border-base-border p-6';

      const title = document.createElement('h3');
      title.id = `chart-${metricName}-title`;
      title.className = 'text-sm font-semibold';
      title.textContent = metricName;
      chartContainer.appendChild(title);

      const chartDiv = document.createElement('div');
      chartDiv.id = `chart-${metricName}`;
      chartDiv.className = 'bg-base-bg';
      chartContainer.appendChild(chartDiv);

      chartsContainer.appendChild(chartContainer);
    }
  });

  test('updates only chart divs, not title elements', () => {
    updateChartHeights(chartsContainer, 200);

    const lossChart = chartsContainer.querySelector('#chart-loss');
    const lossTitle = chartsContainer.querySelector('#chart-loss-title');
    const accuracyChart = chartsContainer.querySelector('#chart-accuracy');
    const accuracyTitle = chartsContainer.querySelector('#chart-accuracy-title');

    expect(lossChart.style.height).toBe('200px');
    expect(accuracyChart.style.height).toBe('200px');
    expect(lossTitle.style.height).toBe('');
    expect(accuracyTitle.style.height).toBe('');
  });

  test('ignores custom selector that would match title elements', () => {
    // The old selector accidentally matched title elements too.
    updateChartHeights(chartsContainer, 200, '[id^="chart-"]');

    const lossTitle = chartsContainer.querySelector('#chart-loss-title');
    expect(lossTitle.style.height).toBe('200px');
  });
});

describe('updateContainerPadding', () => {
  test('updates padding classes for small size', () => {
    const container = document.createElement('div');
    const chart1 = document.createElement('div');
    chart1.className = 'p-6';
    const chart2 = document.createElement('div');
    chart2.className = 'p-6';
    container.appendChild(chart1);
    container.appendChild(chart2);

    updateContainerPadding(container, 'S');
    expect(chart1.classList.contains('p-3')).toBe(true);
    expect(chart1.classList.contains('p-6')).toBe(false);
    expect(chart2.classList.contains('p-3')).toBe(true);
    expect(chart2.classList.contains('p-6')).toBe(false);
  });

  test('updates padding classes for medium/large size', () => {
    const container = document.createElement('div');
    const chart1 = document.createElement('div');
    chart1.className = 'p-3';
    container.appendChild(chart1);

    updateContainerPadding(container, 'M');
    expect(chart1.classList.contains('p-6')).toBe(true);
    expect(chart1.classList.contains('p-3')).toBe(false);
  });
});

describe('updateSizeButtonStyles', () => {
  test('applies active styles to selected size', () => {
    const buttons = {
      S: document.createElement('button'),
      M: document.createElement('button'),
      L: document.createElement('button'),
    };
    updateSizeButtonStyles(buttons, 'M');
    expect(buttons.M.classList.contains('bg-action')).toBe(true);
    expect(buttons.S.classList.contains('bg-action')).toBe(false);
    expect(buttons.L.classList.contains('bg-action')).toBe(false);
  });
});
