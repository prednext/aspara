import { describe, expect, test } from 'vitest';
import {
  INITIAL_SINCE_TIMESTAMP,
  buildSSEUrl,
  createIconUpdateFromStatus,
  extractRunNamesFromElements,
  isConnectionClosed,
  parseStatusUpdate,
} from '../../src/aspara/dashboard/static/js/runs-list/sse-utils.js';

describe('INITIAL_SINCE_TIMESTAMP', () => {
  test('is epoch timestamp as UNIX ms (0)', () => {
    expect(INITIAL_SINCE_TIMESTAMP).toBe(0);
  });
});

describe('buildSSEUrl', () => {
  test('builds URL with single run and since parameter', () => {
    const since = 1705320645123; // UNIX ms
    const result = buildSSEUrl('my-project', ['run-1'], since);
    expect(result).toBe(`/api/projects/my-project/runs/stream?runs=run-1&since=${since}`);
  });

  test('builds URL with multiple runs and since parameter', () => {
    const since = 1705320645123; // UNIX ms
    const result = buildSSEUrl('my-project', ['run-1', 'run-2', 'run-3'], since);
    expect(result).toBe(`/api/projects/my-project/runs/stream?runs=run-1%2Crun-2%2Crun-3&since=${since}`);
  });

  test('encodes special characters in run names', () => {
    const since = 1705320645123; // UNIX ms
    const result = buildSSEUrl('my-project', ['run/1', 'run#2'], since);
    expect(result).toContain('runs=run%2F1%2Crun%232');
    expect(result).toContain('since=');
  });

  test('handles empty runs array', () => {
    const since = 1705320645123; // UNIX ms
    const result = buildSSEUrl('my-project', [], since);
    expect(result).toBe(`/api/projects/my-project/runs/stream?runs=&since=${since}`);
  });

  test('preserves project name in URL', () => {
    const since = 1705320645123; // UNIX ms
    const result = buildSSEUrl('special-project-123', ['run-1'], since);
    expect(result).toContain('/api/projects/special-project-123/');
  });

  test('uses INITIAL_SINCE_TIMESTAMP for first connection', () => {
    const result = buildSSEUrl('my-project', ['run-1'], INITIAL_SINCE_TIMESTAMP);
    expect(result).toContain('since=0');
  });
});

describe('parseStatusUpdate', () => {
  test('parses valid JSON status data', () => {
    const eventData = JSON.stringify({
      run: 'run-1',
      status: 'completed',
    });

    const result = parseStatusUpdate(eventData);

    expect(result.run).toBe('run-1');
    expect(result.status).toBe('completed');
  });

  test('returns null on invalid JSON', () => {
    const result = parseStatusUpdate('invalid json');
    expect(result).toBeNull();
  });

  test('returns null for empty object (missing required fields)', () => {
    const result = parseStatusUpdate('{}');
    expect(result).toBeNull();
  });

  test('returns null for missing status field', () => {
    const eventData = JSON.stringify({
      run: 'run-1',
      metadata: { key: 'value' },
    });

    const result = parseStatusUpdate(eventData);
    expect(result).toBeNull();
  });

  test('returns null for invalid status value', () => {
    const eventData = JSON.stringify({
      run: 'run-1',
      status: 'invalid_status',
    });

    const result = parseStatusUpdate(eventData);
    expect(result).toBeNull();
  });

  test('parses valid data with extra fields', () => {
    const eventData = JSON.stringify({
      run: 'run-1',
      status: 'wip',
      metadata: { key: 'value' },
    });

    const result = parseStatusUpdate(eventData);
    expect(result.run).toBe('run-1');
    expect(result.status).toBe('wip');
    expect(result.metadata.key).toBe('value');
  });
});

describe('createIconUpdateFromStatus', () => {
  test('creates update for wip status', () => {
    const statusData = { status: 'wip' };

    const result = createIconUpdateFromStatus(statusData);

    expect(result.innerHTML).toBe('<svg class="w-4 h-4 flex-shrink-0"><use href="#status-icon-wip"></use></svg>');
    expect(result.status).toBe('wip');
  });

  test('creates update for completed status', () => {
    const statusData = { status: 'completed' };

    const result = createIconUpdateFromStatus(statusData);

    expect(result.innerHTML).toBe('<svg class="w-4 h-4 flex-shrink-0"><use href="#status-icon-completed"></use></svg>');
    expect(result.status).toBe('completed');
  });

  test('creates update for failed status', () => {
    const statusData = { status: 'failed' };

    const result = createIconUpdateFromStatus(statusData);

    expect(result.innerHTML).toBe('<svg class="w-4 h-4 flex-shrink-0"><use href="#status-icon-failed"></use></svg>');
    expect(result.status).toBe('failed');
  });

  test('creates update for maybe_failed status', () => {
    const statusData = { status: 'maybe_failed' };

    const result = createIconUpdateFromStatus(statusData);

    expect(result.innerHTML).toBe('<svg class="w-4 h-4 flex-shrink-0"><use href="#icon-exclamation-triangle"></use></svg>');
    expect(result.status).toBe('maybe_failed');
  });
});

describe('extractRunNamesFromElements', () => {
  function createMockElement(runName) {
    return { dataset: { run: runName } };
  }

  test('extracts run names from elements', () => {
    const elements = [createMockElement('run-1'), createMockElement('run-2'), createMockElement('run-3')];

    const result = extractRunNamesFromElements(elements);

    expect(result).toEqual(['run-1', 'run-2', 'run-3']);
  });

  test('handles empty array', () => {
    const result = extractRunNamesFromElements([]);
    expect(result).toEqual([]);
  });

  test('handles single element', () => {
    const elements = [createMockElement('only-run')];
    const result = extractRunNamesFromElements(elements);
    expect(result).toEqual(['only-run']);
  });

  test('handles NodeList-like object', () => {
    const nodeListLike = {
      0: createMockElement('run-a'),
      1: createMockElement('run-b'),
      length: 2,
      [Symbol.iterator]: function* () {
        yield this[0];
        yield this[1];
      },
    };

    const result = extractRunNamesFromElements(nodeListLike);
    expect(result).toEqual(['run-a', 'run-b']);
  });
});

describe('isConnectionClosed', () => {
  test('returns true for CLOSED state (2)', () => {
    expect(isConnectionClosed(2)).toBe(true);
  });

  test('returns false for CONNECTING state (0)', () => {
    expect(isConnectionClosed(0)).toBe(false);
  });

  test('returns false for OPEN state (1)', () => {
    expect(isConnectionClosed(1)).toBe(false);
  });
});
