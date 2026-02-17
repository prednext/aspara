import { describe, expect, test } from 'vitest';
import { createSortComparator, matchesSearch, parseProjectElement } from '../../src/aspara/dashboard/static/js/projects-list-utils.js';

describe('matchesSearch', () => {
  test('returns true when query is empty', () => {
    const project = { name: 'test', tags: ['tag1'] };
    expect(matchesSearch(project, '')).toBe(true);
  });

  test('returns true when query is null', () => {
    const project = { name: 'test', tags: ['tag1'] };
    expect(matchesSearch(project, null)).toBe(true);
  });

  test('returns true when query is undefined', () => {
    const project = { name: 'test', tags: ['tag1'] };
    expect(matchesSearch(project, undefined)).toBe(true);
  });

  test('matches project name case-insensitively', () => {
    const project = { name: 'MyProject', tags: [] };
    expect(matchesSearch(project, 'myproject')).toBe(true);
    expect(matchesSearch(project, 'MYPROJECT')).toBe(true);
    expect(matchesSearch(project, 'MyProject')).toBe(true);
  });

  test('matches partial project name', () => {
    const project = { name: 'MyAwesomeProject', tags: [] };
    expect(matchesSearch(project, 'awesome')).toBe(true);
    expect(matchesSearch(project, 'proj')).toBe(true);
    expect(matchesSearch(project, 'my')).toBe(true);
  });

  test('matches project tags', () => {
    const project = { name: 'test', tags: ['production', 'v1.0', 'important'] };
    expect(matchesSearch(project, 'production')).toBe(true);
    expect(matchesSearch(project, 'prod')).toBe(true);
    expect(matchesSearch(project, 'v1')).toBe(true);
    expect(matchesSearch(project, 'important')).toBe(true);
  });

  test('matches tags case-insensitively', () => {
    const project = { name: 'test', tags: ['Production', 'V1.0'] };
    expect(matchesSearch(project, 'production')).toBe(true);
    expect(matchesSearch(project, 'PRODUCTION')).toBe(true);
  });

  test('returns false when no match', () => {
    const project = { name: 'test', tags: ['tag1', 'tag2'] };
    expect(matchesSearch(project, 'nonexistent')).toBe(false);
    expect(matchesSearch(project, 'xyz')).toBe(false);
  });

  test('handles project without tags array', () => {
    const project = { name: 'test', tags: null };
    expect(matchesSearch(project, 'test')).toBe(true);
    expect(matchesSearch(project, 'other')).toBe(false);
  });

  test('handles empty tags array', () => {
    const project = { name: 'test', tags: [] };
    expect(matchesSearch(project, 'test')).toBe(true);
    expect(matchesSearch(project, 'tag')).toBe(false);
  });
});

describe('createSortComparator', () => {
  const projects = [
    { name: 'Beta', runCount: 10, lastUpdate: 1000 },
    { name: 'Alpha', runCount: 5, lastUpdate: 2000 },
    { name: 'Gamma', runCount: 20, lastUpdate: 500 },
  ];

  describe('sort by name', () => {
    test('sorts by name ascending', () => {
      const sorted = [...projects].sort(createSortComparator('name', 'asc'));
      expect(sorted.map((p) => p.name)).toEqual(['Alpha', 'Beta', 'Gamma']);
    });

    test('sorts by name descending', () => {
      const sorted = [...projects].sort(createSortComparator('name', 'desc'));
      expect(sorted.map((p) => p.name)).toEqual(['Gamma', 'Beta', 'Alpha']);
    });

    test('sorts case-insensitively', () => {
      const mixedCase = [{ name: 'zebra' }, { name: 'ALPHA' }, { name: 'Beta' }];
      const sorted = [...mixedCase].sort(createSortComparator('name', 'asc'));
      expect(sorted.map((p) => p.name)).toEqual(['ALPHA', 'Beta', 'zebra']);
    });
  });

  describe('sort by runCount', () => {
    test('sorts by runCount ascending', () => {
      const sorted = [...projects].sort(createSortComparator('runCount', 'asc'));
      expect(sorted.map((p) => p.runCount)).toEqual([5, 10, 20]);
    });

    test('sorts by runCount descending', () => {
      const sorted = [...projects].sort(createSortComparator('runCount', 'desc'));
      expect(sorted.map((p) => p.runCount)).toEqual([20, 10, 5]);
    });
  });

  describe('sort by lastUpdate', () => {
    test('sorts by lastUpdate ascending', () => {
      const sorted = [...projects].sort(createSortComparator('lastUpdate', 'asc'));
      expect(sorted.map((p) => p.lastUpdate)).toEqual([500, 1000, 2000]);
    });

    test('sorts by lastUpdate descending', () => {
      const sorted = [...projects].sort(createSortComparator('lastUpdate', 'desc'));
      expect(sorted.map((p) => p.lastUpdate)).toEqual([2000, 1000, 500]);
    });
  });

  describe('edge cases', () => {
    test('returns 0 for unknown sort key', () => {
      const comparator = createSortComparator('unknown', 'asc');
      expect(comparator(projects[0], projects[1])).toBe(0);
    });

    test('handles equal values', () => {
      const equalProjects = [
        { name: 'Alpha', runCount: 10 },
        { name: 'Alpha', runCount: 10 },
      ];
      const comparator = createSortComparator('name', 'asc');
      expect(comparator(equalProjects[0], equalProjects[1])).toBe(0);
    });
  });
});

describe('parseProjectElement', () => {
  function createMockElement(data) {
    return {
      dataset: data,
    };
  }

  test('parses basic project data', () => {
    const element = createMockElement({
      project: 'my-project',
      runCount: '10',
      lastUpdate: '1705312800000',
      tags: 'tag1 tag2 tag3',
    });

    const result = parseProjectElement(element);

    expect(result.element).toBe(element);
    expect(result.name).toBe('my-project');
    expect(result.runCount).toBe(10);
    expect(result.tags).toEqual(['tag1', 'tag2', 'tag3']);
  });

  test('handles missing runCount', () => {
    const element = createMockElement({
      project: 'my-project',
      lastUpdate: '1705312800000',
      tags: '',
    });

    const result = parseProjectElement(element);
    expect(result.runCount).toBe(0);
  });

  test('handles invalid runCount', () => {
    const element = createMockElement({
      project: 'my-project',
      runCount: 'invalid',
      lastUpdate: '1705312800000',
      tags: '',
    });

    const result = parseProjectElement(element);
    expect(result.runCount).toBe(0);
  });

  test('handles missing tags', () => {
    const element = createMockElement({
      project: 'my-project',
      runCount: '5',
      lastUpdate: '1705312800000',
    });

    const result = parseProjectElement(element);
    expect(result.tags).toEqual([]);
  });

  test('handles empty tags string', () => {
    const element = createMockElement({
      project: 'my-project',
      runCount: '5',
      lastUpdate: '1705312800000',
      tags: '',
    });

    const result = parseProjectElement(element);
    expect(result.tags).toEqual([]);
  });

  test('trims whitespace from tags', () => {
    const element = createMockElement({
      project: 'my-project',
      runCount: '5',
      lastUpdate: '1705312800000',
      tags: '  tag1   tag2  ',
    });

    const result = parseProjectElement(element);
    expect(result.tags).toEqual(['tag1', 'tag2']);
  });

  test('filters out empty tags', () => {
    const element = createMockElement({
      project: 'my-project',
      runCount: '5',
      lastUpdate: '1705312800000',
      tags: 'tag1  tag2',
    });

    const result = parseProjectElement(element);
    expect(result.tags).not.toContain('');
  });

  test('parses lastUpdate as UNIX ms timestamp', () => {
    const timestampMs = 1705312800000; // 2024-01-15T10:00:00Z
    const element = createMockElement({
      project: 'my-project',
      runCount: '5',
      lastUpdate: String(timestampMs),
      tags: '',
    });

    const result = parseProjectElement(element);
    expect(result.lastUpdate).toBe(timestampMs);
  });
});
