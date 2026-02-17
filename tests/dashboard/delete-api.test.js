import { beforeEach, describe, expect, test, vi } from 'vitest';
import { deleteProjectApi, deleteRunApi } from '../../src/aspara/dashboard/static/js/api/delete-api.js';

describe('deleteProjectApi', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test('should call API with correct URL and method', async () => {
    const mockResponse = { message: 'Project deleted' };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const result = await deleteProjectApi('test-project');

    expect(fetch).toHaveBeenCalledWith('/api/projects/test-project', {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
    });
    expect(result).toEqual(mockResponse);
  });

  test('should encode special characters in project name', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ message: 'Deleted' }),
    });

    await deleteProjectApi('test/project#1');

    expect(fetch).toHaveBeenCalledWith('/api/projects/test%2Fproject%231', expect.any(Object));
  });

  test('should throw error on API error response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: 'Project not found' }),
    });

    await expect(deleteProjectApi('test-project')).rejects.toThrow('Project not found');
  });

  test('should throw "Unknown error" when response has no detail', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({}),
    });

    await expect(deleteProjectApi('test-project')).rejects.toThrow('Unknown error');
  });

  test('should propagate network errors', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    await expect(deleteProjectApi('test-project')).rejects.toThrow('Network error');
  });
});

describe('deleteRunApi', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test('should call API with correct URL and method', async () => {
    const mockResponse = { message: 'Run deleted' };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const result = await deleteRunApi('project-1', 'run-1');

    expect(fetch).toHaveBeenCalledWith('/api/projects/project-1/runs/run-1', {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
    });
    expect(result).toEqual(mockResponse);
  });

  test('should encode special characters in names', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ message: 'Deleted' }),
    });

    await deleteRunApi('proj/1', 'run#2');

    expect(fetch).toHaveBeenCalledWith('/api/projects/proj%2F1/runs/run%232', expect.any(Object));
  });

  test('should throw error on API error response', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: 'Run not found' }),
    });

    await expect(deleteRunApi('project-1', 'run-1')).rejects.toThrow('Run not found');
  });

  test('should throw "Unknown error" when response has no detail', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({}),
    });

    await expect(deleteRunApi('project-1', 'run-1')).rejects.toThrow('Unknown error');
  });

  test('should propagate network errors', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Connection refused'));

    await expect(deleteRunApi('project-1', 'run-1')).rejects.toThrow('Connection refused');
  });
});
