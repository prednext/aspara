import { describe, expect, test } from 'vitest';
import { STATUS_DISPLAY_NAMES, getStatusDisplayName } from '../../src/aspara/dashboard/static/js/status-utils.js';

describe('STATUS_DISPLAY_NAMES', () => {
  test('has all expected status values', () => {
    expect(STATUS_DISPLAY_NAMES).toHaveProperty('wip');
    expect(STATUS_DISPLAY_NAMES).toHaveProperty('completed');
    expect(STATUS_DISPLAY_NAMES).toHaveProperty('failed');
    expect(STATUS_DISPLAY_NAMES).toHaveProperty('maybe_failed');
  });

  test('has correct display names', () => {
    expect(STATUS_DISPLAY_NAMES.wip).toBe('Running');
    expect(STATUS_DISPLAY_NAMES.completed).toBe('Completed');
    expect(STATUS_DISPLAY_NAMES.failed).toBe('Failed');
    expect(STATUS_DISPLAY_NAMES.maybe_failed).toBe('Maybe Failed');
  });
});

describe('getStatusDisplayName', () => {
  test('returns Running for wip status', () => {
    expect(getStatusDisplayName('wip')).toBe('Running');
  });

  test('returns Completed for completed status', () => {
    expect(getStatusDisplayName('completed')).toBe('Completed');
  });

  test('returns Failed for failed status', () => {
    expect(getStatusDisplayName('failed')).toBe('Failed');
  });

  test('returns Maybe Failed for maybe_failed status', () => {
    expect(getStatusDisplayName('maybe_failed')).toBe('Maybe Failed');
  });

  test('returns status value itself for unknown status', () => {
    expect(getStatusDisplayName('unknown')).toBe('unknown');
    expect(getStatusDisplayName('custom_status')).toBe('custom_status');
  });
});
