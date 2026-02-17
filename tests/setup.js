// Legacy setup file - please use vitest-setup.js for new tests
// This file is kept for backward compatibility with any remaining references

import { vi } from 'vitest';

// Note: Canvas API is now handled by @napi-rs/canvas in vitest-canvas-setup.js
// This legacy file is kept for backward compatibility only
// This file provides fallback mocks only

// ResizeObserver Mock
global.ResizeObserver = vi.fn().mockImplementation((callback) => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// matchMedia Mock
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// requestAnimationFrame Mock
global.requestAnimationFrame = vi.fn((cb) => {
  return setTimeout(cb, 16);
});

global.cancelAnimationFrame = vi.fn((id) => {
  clearTimeout(id);
});

// Performance Mock
global.performance = {
  now: vi.fn(() => Date.now()),
};

// DOM manipulation helpers for tests
export const createTestContainer = (id = 'test-container') => {
  const container = document.createElement('div');
  container.id = id;
  container.style.width = '600px';
  container.style.height = '400px';
  container.style.position = 'absolute';
  container.style.top = '0px';
  container.style.left = '0px';

  // getBoundingClientRectをモック
  container.getBoundingClientRect = () => ({
    width: 600,
    height: 400,
    top: 0,
    left: 0,
    right: 600,
    bottom: 400,
    x: 0,
    y: 0,
  });

  document.body.appendChild(container);
  return container;
};

export const cleanupTestContainer = (id = 'test-container') => {
  const container = document.getElementById(id);
  if (container) {
    container.remove();
  }
};

// Test data generators
export const generateTestMetricsData = (seriesCount = 2, pointsPerSeries = 10) => {
  const series = [];

  for (let s = 0; s < seriesCount; s++) {
    const data = [];
    for (let i = 0; i < pointsPerSeries; i++) {
      data.push({
        step: i,
        value: Math.random() * 0.5 + 0.25, // 0.25-0.75の範囲
        timestamp: new Date(Date.now() + i * 1000).toISOString(),
      });
    }

    series.push({
      name: `metric_${s}`,
      data: data,
    });
  }

  return {
    series,
    metadata: {
      totalPoints: seriesCount * pointsPerSeries,
    },
  };
};

// Location Mock setup function for tests that need it
export const mockLocation = (pathname = '/projects/test_project/experiment_1/compare') => {
  const originalLocation = window.location;

  // Create a mock location object
  const mockLocationObject = {
    pathname,
    href: `http://localhost${pathname}`,
    origin: 'http://localhost',
    search: '',
    hash: '',
    assign: vi.fn(),
    replace: vi.fn(),
    reload: vi.fn(),
  };

  // Replace window.location (ignore navigation errors in test environment)
  window.location = undefined;
  window.location = mockLocationObject;

  // Return cleanup function
  return () => {
    try {
      window.location = undefined;
      window.location = originalLocation;
    } catch (e) {
      // Ignore errors in cleanup
    }
  };
};
