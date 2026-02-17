import { describe, expect, test } from 'vitest';
import {
  binarySearchByStep,
  binarySearchNearestStep,
  calculateDataRanges,
  findNearestStepBinary,
} from '../../src/aspara/dashboard/static/js/chart/interaction-utils.js';

describe('calculateDataRanges', () => {
  test('returns null for empty series', () => {
    expect(calculateDataRanges([])).toBeNull();
  });

  test('returns null for series with no data', () => {
    expect(calculateDataRanges([{ data: { steps: [], values: [] } }])).toBeNull();
    expect(calculateDataRanges([{ data: null }])).toBeNull();
  });

  test('calculates correct ranges for single series', () => {
    // SoA format: steps must be sorted
    const series = [
      {
        data: {
          steps: [0, 5, 10],
          values: [1, 3, 5],
        },
      },
    ];

    const result = calculateDataRanges(series);
    expect(result.xMin).toBe(0);
    expect(result.xMax).toBe(10);
    expect(result.yMin).toBe(1);
    expect(result.yMax).toBe(5);
  });

  test('calculates ranges across multiple series', () => {
    const series = [
      {
        data: {
          steps: [0, 5],
          values: [1, 2],
        },
      },
      {
        data: {
          steps: [3, 10],
          values: [0, 10],
        },
      },
    ];

    const result = calculateDataRanges(series);
    expect(result.xMin).toBe(0);
    expect(result.xMax).toBe(10);
    expect(result.yMin).toBe(0);
    expect(result.yMax).toBe(10);
  });

  test('handles negative values', () => {
    const series = [
      {
        data: {
          steps: [-5, 5],
          values: [-10, 10],
        },
      },
    ];

    const result = calculateDataRanges(series);
    expect(result.xMin).toBe(-5);
    expect(result.xMax).toBe(5);
    expect(result.yMin).toBe(-10);
    expect(result.yMax).toBe(10);
  });
});

describe('binarySearchNearestStep', () => {
  test('returns null for empty data', () => {
    expect(binarySearchNearestStep([], 50)).toBeNull();
    expect(binarySearchNearestStep(null, 50)).toBeNull();
  });

  test('returns the only step for single element', () => {
    const steps = [100];
    expect(binarySearchNearestStep(steps, 50)).toEqual({ index: 0, step: 100 });
    expect(binarySearchNearestStep(steps, 150)).toEqual({ index: 0, step: 100 });
  });

  test('finds exact match', () => {
    const steps = [0, 50, 100];
    expect(binarySearchNearestStep(steps, 50)).toEqual({ index: 1, step: 50 });
  });

  test('finds nearest step when between two points', () => {
    const steps = [0, 50, 100];
    // 30 is closer to 50 than to 0
    expect(binarySearchNearestStep(steps, 30)).toEqual({ index: 1, step: 50 });
    // 20 is closer to 0 than to 50
    expect(binarySearchNearestStep(steps, 20)).toEqual({ index: 0, step: 0 });
    // 25 is equidistant, should return left (0)
    expect(binarySearchNearestStep(steps, 25)).toEqual({ index: 0, step: 0 });
  });

  test('handles target before first element', () => {
    const steps = [10, 50, 100];
    expect(binarySearchNearestStep(steps, 5)).toEqual({ index: 0, step: 10 });
    expect(binarySearchNearestStep(steps, -100)).toEqual({ index: 0, step: 10 });
  });

  test('handles target after last element', () => {
    const steps = [0, 50, 100];
    expect(binarySearchNearestStep(steps, 150)).toEqual({ index: 2, step: 100 });
    expect(binarySearchNearestStep(steps, 1000)).toEqual({ index: 2, step: 100 });
  });

  test('works with large sorted dataset', () => {
    const steps = Array.from({ length: 10000 }, (_, i) => i * 10);
    // step 5000 is at index 500
    expect(binarySearchNearestStep(steps, 5000)).toEqual({ index: 500, step: 5000 });
    // 5004 is closer to 5000 than 5010
    expect(binarySearchNearestStep(steps, 5004)).toEqual({ index: 500, step: 5000 });
    // 5006 is closer to 5010 than 5000
    expect(binarySearchNearestStep(steps, 5006)).toEqual({ index: 501, step: 5010 });
  });
});

describe('binarySearchByStep', () => {
  test('returns null for empty data', () => {
    expect(binarySearchByStep([], [], 50)).toBeNull();
    expect(binarySearchByStep(null, null, 50)).toBeNull();
  });

  test('finds exact match', () => {
    const steps = [0, 50, 100];
    const values = [1, 2, 3];
    expect(binarySearchByStep(steps, values, 50)).toEqual({ index: 1, step: 50, value: 2 });
    expect(binarySearchByStep(steps, values, 0)).toEqual({ index: 0, step: 0, value: 1 });
    expect(binarySearchByStep(steps, values, 100)).toEqual({ index: 2, step: 100, value: 3 });
  });

  test('returns null when step not found', () => {
    const steps = [0, 50, 100];
    const values = [1, 2, 3];
    expect(binarySearchByStep(steps, values, 25)).toBeNull();
    expect(binarySearchByStep(steps, values, 75)).toBeNull();
    expect(binarySearchByStep(steps, values, -10)).toBeNull();
    expect(binarySearchByStep(steps, values, 150)).toBeNull();
  });

  test('works with large sorted dataset', () => {
    const steps = Array.from({ length: 10000 }, (_, i) => i * 10);
    const values = Array.from({ length: 10000 }, (_, i) => i);
    expect(binarySearchByStep(steps, values, 5000)).toEqual({ index: 500, step: 5000, value: 500 });
    expect(binarySearchByStep(steps, values, 5001)).toBeNull();
  });
});

describe('findNearestStepBinary', () => {
  const series = [
    {
      data: {
        steps: [0, 50, 100],
        values: [1, 2, 3],
      },
    },
  ];

  test('finds closest step to mouse position', () => {
    // At middle of plot (x=300 for margin=60, plotWidth=480)
    // step 50 should be at x = 60 + (50/100)*480 = 300
    const result = findNearestStepBinary(300, series, 60, 480, 0, 100);
    expect(result).toBe(50);
  });

  test('finds step at left edge', () => {
    const result = findNearestStepBinary(60, series, 60, 480, 0, 100);
    expect(result).toBe(0);
  });

  test('finds step at right edge', () => {
    const result = findNearestStepBinary(540, series, 60, 480, 0, 100);
    expect(result).toBe(100);
  });

  test('returns null for empty series', () => {
    expect(findNearestStepBinary(300, [], 60, 480, 0, 100)).toBeNull();
  });

  test('returns null for series with no data', () => {
    expect(findNearestStepBinary(300, [{ data: { steps: [], values: [] } }], 60, 480, 0, 100)).toBeNull();
  });

  test('uses first series with data as reference', () => {
    const multiSeries = [{ data: { steps: [], values: [] } }, { data: { steps: [25], values: [2] } }, { data: { steps: [100], values: [3] } }];

    // Should use second series (first with data)
    const result = findNearestStepBinary(170, multiSeries, 60, 480, 0, 100);
    expect(result).toBe(25);
  });

  test('handles series with different steps (LTTB downsampling scenario)', () => {
    // Simulate LTTB downsampling where each series has different steps (SoA format)
    const multiSeries = [
      {
        name: 'run1',
        data: {
          steps: [0, 100, 200, 400, 500],
          values: [1, 2, 3, 4, 5],
        },
      },
      {
        name: 'run2',
        data: {
          steps: [0, 50, 150, 300, 500], // Different steps than run1
          values: [1, 2, 3, 4, 5],
        },
      },
    ];

    const margin = 60;
    const plotWidth = 480;
    const xMin = 0;
    const xMax = 500;

    // Test various mouse positions
    // mouseX=108 corresponds to step=50 ((108-60)/480 * 500 = 50)
    const testCases = [
      { mouseX: 108, expectedStep: 50 }, // step 50 is only in run2
      { mouseX: 204, expectedStep: 150 }, // step 150 is only in run2
      { mouseX: 348, expectedStep: 300 }, // step 300 is only in run2
    ];

    for (const { mouseX, expectedStep } of testCases) {
      const result = findNearestStepBinary(mouseX, multiSeries, margin, plotWidth, xMin, xMax);
      expect(result).toBe(expectedStep);
    }
  });
});

describe('Performance: Binary search', () => {
  /**
   * Generate test data with specified number of points (SoA format)
   */
  function generateTestData(pointCount, seriesCount = 1) {
    return Array.from({ length: seriesCount }, (_, seriesIndex) => ({
      name: `series-${seriesIndex}`,
      data: {
        steps: Array.from({ length: pointCount }, (_, i) => i),
        values: Array.from({ length: pointCount }, (_, i) => Math.sin(i * 0.1) * 100 + seriesIndex * 10),
      },
    }));
  }

  /**
   * Measure execution time of a function over multiple iterations
   */
  function measurePerformance(fn, iterations = 1000) {
    const start = performance.now();
    for (let i = 0; i < iterations; i++) {
      fn();
    }
    const end = performance.now();
    return (end - start) / iterations;
  }

  test('performance scales logarithmically for binary search', () => {
    const smallCount = 1000;
    const largeCount = 100000;
    const iterations = 1000;
    const margin = 60;
    const plotWidth = 480;

    const smallSeries = generateTestData(smallCount);
    const largeSeries = generateTestData(largeCount);

    const smallTime = measurePerformance(() => {
      findNearestStepBinary(300, smallSeries, margin, plotWidth, 0, smallCount - 1);
    }, iterations);

    const largeTime = measurePerformance(() => {
      findNearestStepBinary(300, largeSeries, margin, plotWidth, 0, largeCount - 1);
    }, iterations);

    // For O(log n), going from 1000 to 100000 (100x data)
    // should only increase time by log(100000)/log(1000) ≈ 1.67x
    // Allow some margin for test stability
    // Guard against division by zero when times are too small to measure
    const timeRatio = smallTime > 0 ? largeTime / smallTime : 1;

    // If both times are essentially 0, binary search is fast enough - that's a pass
    if (smallTime === 0 && largeTime === 0) {
      // Both are too fast to measure - that's actually great performance!
      console.log('Scalability test (binary search):');
      console.log(`  Both ${smallCount} and ${largeCount} points are too fast to measure - excellent!`);
    } else {
      expect(timeRatio).toBeLessThan(20); // CI環境での変動を許容 (O(log n)なので100xにはならない)

      console.log('Scalability test (binary search):');
      console.log(`  ${smallCount} points: ${smallTime.toFixed(4)}ms`);
      console.log(`  ${largeCount} points: ${largeTime.toFixed(4)}ms`);
      console.log(`  Time ratio: ${timeRatio.toFixed(2)}x (expected ~1.67x for O(log n))`);
    }
  });

  test('performance with multiple series', () => {
    const pointCount = 5000;
    const seriesCount = 10;
    const series = generateTestData(pointCount, seriesCount);
    const margin = 60;
    const plotWidth = 480;
    const xMin = 0;
    const xMax = pointCount - 1;
    const iterations = 100;

    const time = measurePerformance(() => {
      findNearestStepBinary(300, series, margin, plotWidth, xMin, xMax);
    }, iterations);

    console.log(`Multiple series performance (${seriesCount} series × ${pointCount} points):`);
    console.log(`  Binary search: ${time.toFixed(4)}ms`);

    // Should complete within reasonable time (< 1ms per call)
    expect(time).toBeLessThan(1);
  });
});
