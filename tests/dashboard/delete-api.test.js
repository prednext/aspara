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

  test('should handle non-JSON error response gracefully', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new SyntaxError('Unexpected token < in JSON')),
    });

    // Should throw a meaningful error, not the raw JSON parse SyntaxError.
    await expect(deleteProjectApi('test-project')).rejects.toThrow(/Server error|Unknown error|Failed to delete/i);
  });

  test('should include raw response body in dev mode', async () => {
    document.body.setAttribute('data-dev-mode', 'true');
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: () => Promise.reject(new SyntaxError('Unexpected token < in JSON')),
      text: () => Promise.resolve('<html><body>Bad Gateway</body></html>'),
    });

    await expect(deleteProjectApi('test-project')).rejects.toThrow(/raw:.*Bad Gateway/i);
    document.body.removeAttribute('data-dev-mode');
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

  test('should handle non-JSON error response gracefully', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: () => Promise.reject(new SyntaxError('Unexpected token < in JSON')),
    });

    // Should throw a meaningful error, not the raw JSON parse SyntaxError.
    await expect(deleteRunApi('project-1', 'run-1')).rejects.toThrow(/Server error|Unknown error|Failed to delete/i);
  });

  test('should include raw response body in dev mode', async () => {
    document.body.setAttribute('data-dev-mode', 'true');
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: () => Promise.reject(new SyntaxError('Unexpected token < in JSON')),
      text: () => Promise.resolve('<html><body>Proxy Error</body></html>'),
    });

    await expect(deleteRunApi('project-1', 'run-1')).rejects.toThrow(/raw:.*Proxy Error/i);
    document.body.removeAttribute('data-dev-mode');
  });
});
