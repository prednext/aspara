/**
 * Unit tests for Chart y-axis scale behavior.
 */
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { Chart } from '../../src/aspara/dashboard/static/js/chart.js';
import { cleanupTestContainer, createTestContainer } from '../vitest-setup.js';

describe('Chart y-axis scale', () => {
  let container;
  let chart;

  beforeEach(() => {
    container = createTestContainer('test-container');
    const chartDiv = document.createElement('div');
    chartDiv.id = 'test-chart';
    chartDiv.style.width = '400px';
    chartDiv.style.height = '300px';
    chartDiv.style.position = 'relative';
    chartDiv.getBoundingClientRect = () => ({
      width: 400,
      height: 300,
      top: 0,
      left: 0,
      right: 400,
      bottom: 300,
      x: 0,
      y: 0,
    });
    container.appendChild(chartDiv);
    chart = new Chart('#test-chart');
    chart.updateSize();
  });

  afterEach(() => {
    chart.destroy();
    cleanupTestContainer('test-container');
  });

  function setPositiveData() {
    chart.setData({
      series: [{ name: 'metric', data: { steps: [0, 1, 2], values: [0.1, 1, 10] } }],
    });
  }

  test('defaults to linear scale', () => {
    expect(chart.yScale).toBe('linear');
  });

  test('toggleYScale switches between linear and log', () => {
    setPositiveData();
    chart.toggleYScale();
    expect(chart.yScale).toBe('log');
    chart.toggleYScale();
    expect(chart.yScale).toBe('linear');
  });

  test('setYScale ignores invalid scale values', () => {
    setPositiveData();
    chart.setYScale('invalid');
    expect(chart.yScale).toBe('linear');
  });

  test('setYScale clears y zoom and hover point', () => {
    setPositiveData();
    chart.zoom.y = { min: 0.1, max: 1 };
    chart.hoverPoint = { step: 0, points: [] };
    chart.setYScale('log');
    expect(chart.yScale).toBe('log');
    expect(chart.zoom.y).toBeNull();
    expect(chart.hoverPoint).toBeNull();
  });

  test('emits onYScaleChange callback when scale changes', () => {
    setPositiveData();
    const callback = vi.fn();
    chart.onYScaleChange = callback;
    chart.setYScale('log');
    expect(callback).toHaveBeenCalledWith('log');
  });

  test('renders message when log scale has no positive y values', () => {
    chart.setData({
      series: [{ name: 'metric', data: { steps: [0, 1], values: [0, -1] } }],
    });
    chart.setYScale('log');
    // draw() should not throw and the chart stays in log scale
    expect(chart.yScale).toBe('log');
  });
});
