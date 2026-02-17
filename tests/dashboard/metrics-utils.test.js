/**
 * Metrics utilities unit tests.
 * Tests for delta decompression and data transformation functions.
 */

import { describe, expect, test } from 'vitest';
import { convertToChartFormat, decompressDeltaData, findLatestTimestamp, mergeDataPoint } from '../../src/aspara/dashboard/static/js/metrics/metrics-utils.js';

describe('decompressDeltaData', () => {
  test('should decompress delta-compressed steps and timestamps', () => {
    const input = {
      loss: {
        'run-1': {
          steps: [0, 1, 1, 1], // deltas: 0, 1, 2, 3
          values: [1.0, 0.8, 0.6, 0.4],
          timestamps: [1000, 100, 100, 100], // deltas: 1000, 1100, 1200, 1300
        },
      },
    };

    const result = decompressDeltaData(input);

    expect(result.loss['run-1'].steps).toEqual([0, 1, 2, 3]);
    expect(result.loss['run-1'].values).toEqual([1.0, 0.8, 0.6, 0.4]);
    expect(result.loss['run-1'].timestamps).toEqual([1000, 1100, 1200, 1300]);
  });

  test('should handle multiple metrics and runs', () => {
    const input = {
      loss: {
        'run-1': { steps: [0, 1], values: [1.0, 0.9], timestamps: [1000, 100] },
        'run-2': { steps: [0, 2], values: [1.1, 0.8], timestamps: [2000, 200] },
      },
      accuracy: {
        'run-1': { steps: [0, 1], values: [0.5, 0.6], timestamps: [1000, 100] },
      },
    };

    const result = decompressDeltaData(input);

    expect(result.loss['run-1'].steps).toEqual([0, 1]);
    expect(result.loss['run-2'].steps).toEqual([0, 2]);
    expect(result.accuracy['run-1'].steps).toEqual([0, 1]);
  });

  test('should handle empty input', () => {
    const result = decompressDeltaData({});
    expect(result).toEqual({});
  });
});

describe('convertToChartFormat', () => {
  test('should convert run data to chart format', () => {
    const runData = {
      'run-1': { steps: [0, 1, 2], values: [1.0, 0.8, 0.6], timestamps: [1000, 1100, 1200] },
      'run-2': { steps: [0, 1], values: [1.1, 0.9], timestamps: [2000, 2100] },
    };

    const result = convertToChartFormat('loss', runData);

    expect(result.title).toBe('loss');
    expect(result.series).toHaveLength(2);
    expect(result.series[0]).toEqual({
      name: 'run-1',
      data: { steps: [0, 1, 2], values: [1.0, 0.8, 0.6] },
    });
    expect(result.series[1]).toEqual({
      name: 'run-2',
      data: { steps: [0, 1], values: [1.1, 0.9] },
    });
  });

  test('should skip empty runs', () => {
    const runData = {
      'run-1': { steps: [0, 1], values: [1.0, 0.8], timestamps: [1000, 1100] },
      'run-2': { steps: [], values: [], timestamps: [] },
    };

    const result = convertToChartFormat('loss', runData);

    expect(result.series).toHaveLength(1);
    expect(result.series[0].name).toBe('run-1');
  });
});

describe('findLatestTimestamp', () => {
  test('should find the latest timestamp across all metrics and runs', () => {
    const metricsData = {
      loss: {
        'run-1': { steps: [0, 1], values: [1.0, 0.8], timestamps: [1000, 1100] },
        'run-2': { steps: [0, 1], values: [1.1, 0.9], timestamps: [2000, 2500] },
      },
      accuracy: {
        'run-1': { steps: [0], values: [0.5], timestamps: [1500] },
      },
    };

    const result = findLatestTimestamp(metricsData);
    expect(result).toBe(2500);
  });

  test('should return 0 for empty data', () => {
    expect(findLatestTimestamp({})).toBe(0);
  });

  test('should handle missing timestamps', () => {
    const metricsData = {
      loss: {
        'run-1': { steps: [0, 1], values: [1.0, 0.8] },
      },
    };

    const result = findLatestTimestamp(metricsData);
    expect(result).toBe(0);
  });
});

describe('mergeDataPoint', () => {
  test('should insert new data point at correct sorted position', () => {
    const cached = {
      steps: [0, 2, 4],
      values: [1.0, 0.8, 0.6],
      timestamps: [1000, 1200, 1400],
    };

    mergeDataPoint(cached, 3, 0.7, 1300);

    expect(cached.steps).toEqual([0, 2, 3, 4]);
    expect(cached.values).toEqual([1.0, 0.8, 0.7, 0.6]);
    expect(cached.timestamps).toEqual([1000, 1200, 1300, 1400]);
  });

  test('should append at end for larger step', () => {
    const cached = {
      steps: [0, 1, 2],
      values: [1.0, 0.9, 0.8],
      timestamps: [1000, 1100, 1200],
    };

    mergeDataPoint(cached, 3, 0.7, 1300);

    expect(cached.steps).toEqual([0, 1, 2, 3]);
    expect(cached.values).toEqual([1.0, 0.9, 0.8, 0.7]);
  });

  test('should update existing step value', () => {
    const cached = {
      steps: [0, 1, 2],
      values: [1.0, 0.9, 0.8],
      timestamps: [1000, 1100, 1200],
    };

    mergeDataPoint(cached, 1, 0.85, 1150);

    expect(cached.steps).toEqual([0, 1, 2]);
    expect(cached.values).toEqual([1.0, 0.85, 0.8]);
    expect(cached.timestamps).toEqual([1000, 1150, 1200]);
  });

  test('should insert at beginning for smaller step', () => {
    const cached = {
      steps: [2, 3, 4],
      values: [0.8, 0.7, 0.6],
      timestamps: [1200, 1300, 1400],
    };

    mergeDataPoint(cached, 1, 0.9, 1100);

    expect(cached.steps).toEqual([1, 2, 3, 4]);
    expect(cached.values).toEqual([0.9, 0.8, 0.7, 0.6]);
  });

  test('should handle empty cache', () => {
    const cached = {
      steps: [],
      values: [],
      timestamps: [],
    };

    mergeDataPoint(cached, 0, 1.0, 1000);

    expect(cached.steps).toEqual([0]);
    expect(cached.values).toEqual([1.0]);
    expect(cached.timestamps).toEqual([1000]);
  });
});
