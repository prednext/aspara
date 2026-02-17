import { describe, expect, test } from 'vitest';
import { createRunSortComparator, parseRunElement } from '../../src/aspara/dashboard/static/js/runs-list/utils.js';

describe('createRunSortComparator', () => {
  const runs = [
    { name: 'run-beta', paramCount: 5, lastUpdate: 1000 },
    { name: 'run-alpha', paramCount: 10, lastUpdate: 2000 },
    { name: 'run-gamma', paramCount: 3, lastUpdate: 500 },
  ];

  describe('sort by name', () => {
    test('sorts by name ascending', () => {
      const sorted = [...runs].sort(createRunSortComparator('name', 'asc'));
      expect(sorted.map((r) => r.name)).toEqual(['run-alpha', 'run-beta', 'run-gamma']);
    });

    test('sorts by name descending', () => {
      const sorted = [...runs].sort(createRunSortComparator('name', 'desc'));
      expect(sorted.map((r) => r.name)).toEqual(['run-gamma', 'run-beta', 'run-alpha']);
    });

    test('sorts case-insensitively', () => {
      const mixedCase = [{ name: 'Zebra' }, { name: 'alpha' }, { name: 'BETA' }];
      const sorted = [...mixedCase].sort(createRunSortComparator('name', 'asc'));
      expect(sorted.map((r) => r.name)).toEqual(['alpha', 'BETA', 'Zebra']);
    });
  });

  describe('sort by paramCount', () => {
    test('sorts by paramCount ascending', () => {
      const sorted = [...runs].sort(createRunSortComparator('paramCount', 'asc'));
      expect(sorted.map((r) => r.paramCount)).toEqual([3, 5, 10]);
    });

    test('sorts by paramCount descending', () => {
      const sorted = [...runs].sort(createRunSortComparator('paramCount', 'desc'));
      expect(sorted.map((r) => r.paramCount)).toEqual([10, 5, 3]);
    });
  });

  describe('sort by lastUpdate', () => {
    test('sorts by lastUpdate ascending', () => {
      const sorted = [...runs].sort(createRunSortComparator('lastUpdate', 'asc'));
      expect(sorted.map((r) => r.lastUpdate)).toEqual([500, 1000, 2000]);
    });

    test('sorts by lastUpdate descending', () => {
      const sorted = [...runs].sort(createRunSortComparator('lastUpdate', 'desc'));
      expect(sorted.map((r) => r.lastUpdate)).toEqual([2000, 1000, 500]);
    });
  });

  describe('edge cases', () => {
    test('returns 0 for unknown sort key', () => {
      const comparator = createRunSortComparator('unknown', 'asc');
      expect(comparator(runs[0], runs[1])).toBe(0);
    });

    test('handles equal values', () => {
      const equalRuns = [
        { name: 'run-a', paramCount: 10 },
        { name: 'run-a', paramCount: 10 },
      ];
      const comparator = createRunSortComparator('name', 'asc');
      expect(comparator(equalRuns[0], equalRuns[1])).toBe(0);
    });

    test('handles empty array', () => {
      const sorted = [].sort(createRunSortComparator('name', 'asc'));
      expect(sorted).toEqual([]);
    });

    test('handles single element', () => {
      const sorted = [runs[0]].sort(createRunSortComparator('name', 'asc'));
      expect(sorted).toEqual([runs[0]]);
    });
  });
});

describe('parseRunElement', () => {
  function createMockElement(data) {
    return {
      dataset: data,
    };
  }

  test('parses basic run data', () => {
    const element = createMockElement({
      run: 'my-run',
      paramCount: '5',
      lastUpdate: '1705312800000',
    });

    const result = parseRunElement(element);

    expect(result.element).toBe(element);
    expect(result.name).toBe('my-run');
    expect(result.paramCount).toBe(5);
  });

  test('handles missing paramCount', () => {
    const element = createMockElement({
      run: 'my-run',
      lastUpdate: '1705312800000',
    });

    const result = parseRunElement(element);
    expect(result.paramCount).toBe(0);
  });

  test('handles invalid paramCount', () => {
    const element = createMockElement({
      run: 'my-run',
      paramCount: 'invalid',
      lastUpdate: '1705312800000',
    });

    const result = parseRunElement(element);
    expect(result.paramCount).toBe(0);
  });

  test('parses lastUpdate as UNIX ms timestamp', () => {
    const timestampMs = 1705312800000; // 2024-01-15T10:00:00Z
    const element = createMockElement({
      run: 'my-run',
      paramCount: '5',
      lastUpdate: String(timestampMs),
    });

    const result = parseRunElement(element);
    expect(result.lastUpdate).toBe(timestampMs);
  });

  test('preserves element reference', () => {
    const element = createMockElement({
      run: 'my-run',
      paramCount: '5',
      lastUpdate: '1705312800000',
    });

    const result = parseRunElement(element);
    expect(result.element).toBe(element);
  });
});
