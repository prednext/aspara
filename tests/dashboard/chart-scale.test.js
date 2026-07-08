/**
 * Unit tests for chart scale utilities.
 */
import { describe, expect, test } from 'vitest';
import {
  YScale,
  chartYToValue,
  computePaddedYRange,
  formatLogTick,
  fromLogDomain,
  generateLogTicks,
  isLogScale,
  isValidLogValue,
  toLogDomain,
  valueToChartY,
} from '../../src/aspara/dashboard/static/js/chart/scale.js';

describe('scale type helpers', () => {
  test('isLogScale returns true only for log', () => {
    expect(isLogScale(YScale.LOG)).toBe(true);
    expect(isLogScale(YScale.LINEAR)).toBe(false);
    expect(isLogScale('unknown')).toBe(false);
  });

  test('isValidLogValue rejects non-positive and non-finite values', () => {
    expect(isValidLogValue(1)).toBe(true);
    expect(isValidLogValue(0.001)).toBe(true);
    expect(isValidLogValue(0)).toBe(false);
    expect(isValidLogValue(-1)).toBe(false);
    expect(isValidLogValue(Number.NaN)).toBe(false);
    expect(isValidLogValue(Number.POSITIVE_INFINITY)).toBe(false);
  });
});

describe('log domain conversions', () => {
  test('toLogDomain and fromLogDomain are inverses', () => {
    expect(fromLogDomain(toLogDomain(1))).toBe(1);
    expect(fromLogDomain(toLogDomain(10))).toBe(10);
    expect(fromLogDomain(toLogDomain(0.1))).toBeCloseTo(0.1);
  });

  test('toLogDomain uses base 10', () => {
    expect(toLogDomain(1)).toBe(0);
    expect(toLogDomain(10)).toBeCloseTo(1);
    expect(toLogDomain(100)).toBeCloseTo(2);
    expect(toLogDomain(0.1)).toBeCloseTo(-1);
  });
});

describe('computePaddedYRange', () => {
  test('linear scale pads in data space', () => {
    const result = computePaddedYRange(0, 100, YScale.LINEAR, 0.1);
    expect(result.yMinPadded).toBe(-10);
    expect(result.yMaxPadded).toBe(110);
  });

  test('linear scale handles zero range', () => {
    const result = computePaddedYRange(5, 5, YScale.LINEAR, 0.1);
    expect(result.yMinPadded).toBe(4);
    expect(result.yMaxPadded).toBe(6);
  });

  test('log scale pads in log space', () => {
    const result = computePaddedYRange(0.1, 100, YScale.LOG, 0.1);
    expect(result.yMinPadded).toBeLessThan(0.1);
    expect(result.yMaxPadded).toBeGreaterThan(100);
  });

  test('log scale handles zero range with default decade', () => {
    const result = computePaddedYRange(10, 10, YScale.LOG, 0.1);
    // logMin/logMax centered on 1 with a 1-decade range, then padded by 0.1 decade
    expect(result.yMinPadded).toBeCloseTo(10 ** 0.4, 6);
    expect(result.yMaxPadded).toBeCloseTo(10 ** 1.6, 6);
  });

  test('log scale throws for non-positive bounds', () => {
    expect(() => computePaddedYRange(0, 10, YScale.LOG, 0.1)).toThrow();
    expect(() => computePaddedYRange(-1, 10, YScale.LOG, 0.1)).toThrow();
  });
});

describe('valueToChartY', () => {
  const plotHeight = 100;
  const margin = 10;

  test('linear scale maps linearly', () => {
    const y = valueToChartY(50, YScale.LINEAR, plotHeight, margin, 0, 100);
    expect(y).toBe(margin + plotHeight - 50);
  });

  test('linear scale maps min to bottom and max to top', () => {
    expect(valueToChartY(0, YScale.LINEAR, plotHeight, margin, 0, 100)).toBe(margin + plotHeight);
    expect(valueToChartY(100, YScale.LINEAR, plotHeight, margin, 0, 100)).toBe(margin);
  });

  test('log scale maps logarithmically', () => {
    const yMid = valueToChartY(10, YScale.LOG, plotHeight, margin, 1, 100);
    const yTop = valueToChartY(100, YScale.LOG, plotHeight, margin, 1, 100);
    const yBottom = valueToChartY(1, YScale.LOG, plotHeight, margin, 1, 100);
    expect(yBottom).toBe(margin + plotHeight);
    expect(yTop).toBe(margin);
    expect(yMid).toBe(margin + plotHeight / 2);
  });
});

describe('chartYToValue', () => {
  const plotHeight = 100;
  const margin = 10;

  test('linear scale is inverse of valueToChartY', () => {
    const value = chartYToValue(60, YScale.LINEAR, plotHeight, margin, 0, 100);
    expect(value).toBe(50);
  });

  test('log scale is inverse of valueToChartY', () => {
    const value = chartYToValue(margin + plotHeight / 2, YScale.LOG, plotHeight, margin, 1, 100);
    expect(value).toBeCloseTo(10);
  });
});

describe('formatLogTick', () => {
  test('formats powers of ten readably', () => {
    expect(formatLogTick(1)).toBe('1');
    expect(formatLogTick(10)).toBe('10');
    expect(formatLogTick(0.1)).toBe('0.1');
    expect(formatLogTick(0.01)).toBe('0.01');
  });

  test('uses exponential notation for very small values', () => {
    expect(formatLogTick(0.001)).toBe('1e-3');
    expect(formatLogTick(1e-6)).toBe('1e-6');
  });
});

describe('generateLogTicks', () => {
  test('generates powers of ten within range', () => {
    const ticks = generateLogTicks(0.05, 50, 10);
    const values = ticks.map((t) => t.value);
    expect(values).toContain(0.1);
    expect(values).toContain(1);
    expect(values).toContain(10);
  });

  test('falls back to endpoints when no power of ten is inside range', () => {
    const ticks = generateLogTicks(2, 5, 10);
    expect(ticks).toHaveLength(2);
    expect(ticks[0].value).toBe(2);
    expect(ticks[1].value).toBe(5);
  });

  test('limits number of ticks', () => {
    const ticks = generateLogTicks(1e-6, 1e6, 5);
    expect(ticks.length).toBeLessThanOrEqual(5);
  });
});
