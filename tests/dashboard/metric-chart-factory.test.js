/**
 * Metric chart factory unit tests.
 * Tests for chart DOM element creation functions.
 */

import { beforeEach, describe, expect, test } from 'vitest';
import { createChartErrorDisplay, createMetricChartContainer } from '../../src/aspara/dashboard/static/js/metrics/metric-chart-factory.js';

describe('createMetricChartContainer', () => {
  test('should create container with correct structure', () => {
    const { container, chartDiv, chartId } = createMetricChartContainer('loss', 300);

    expect(container.tagName).toBe('DIV');
    expect(container.className).toContain('bg-base-surface');

    const title = container.querySelector('h3');
    expect(title.textContent).toBe('loss');
    expect(title.className).toContain('uppercase');

    expect(chartDiv.id).toBe(chartId);
    expect(chartDiv.style.height).toBe('300px');
    expect(chartDiv.style.width).toBe('100%');
  });

  test('should sanitize metric name for chart ID', () => {
    const { chartId } = createMetricChartContainer('train/loss.metric', 200);
    expect(chartId).toBe('chart-train_loss_metric');
  });

  test('should apply specified chart height', () => {
    const { chartDiv } = createMetricChartContainer('accuracy', 450);
    expect(chartDiv.style.height).toBe('450px');
  });
});

describe('createChartErrorDisplay', () => {
  test('should create error display with metric name and message', () => {
    const container = createChartErrorDisplay('loss', 'Network error');

    expect(container.tagName).toBe('DIV');
    expect(container.className).toContain('bg-base-surface');

    const title = container.querySelector('h3');
    expect(title.textContent).toBe('loss');

    const errorDiv = container.querySelector('.text-status-error');
    expect(errorDiv.textContent).toContain('Network error');
  });

  test('should escape HTML in metric name and error message', () => {
    const container = createChartErrorDisplay('<script>alert(1)</script>', '<img onerror=alert(1)>');

    // HTML tags should be escaped (not interpreted as real HTML)
    expect(container.innerHTML).not.toContain('<script>alert');
    expect(container.innerHTML).not.toContain('<img ');
    expect(container.innerHTML).toContain('&lt;script&gt;');
    expect(container.innerHTML).toContain('&lt;img');
  });
});
