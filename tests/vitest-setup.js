import { encode as msgpackEncode } from '@msgpack/msgpack';
// Vitest test setup file
import { vi } from 'vitest';

// Canvas API is now handled by vitest-canvas-setup.js with @napi-rs/canvas

// EventSource Mock for SSE testing
global.EventSource = vi.fn().mockImplementation((url) => {
  const instance = {
    url,
    readyState: 0, // CONNECTING
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    close: vi.fn(() => {
      instance.readyState = 2; // CLOSED
    }),
  };
  // Immediately set to OPEN state
  instance.readyState = 1;
  return instance;
});

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

// localStorage Mock
const localStorageMock = (() => {
  let store = {};

  return {
    getItem: (key) => store[key] || null,
    setItem: (key, value) => {
      store[key] = value.toString();
    },
    removeItem: (key) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

global.localStorage = localStorageMock;

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

// Fetch Mock helper for API testing
export const mockFetch = (responseData, options = {}) => {
  const { status = 200, ok = true } = options;

  const encoded = msgpackEncode(responseData);
  const arrayBuffer = encoded.buffer.slice(encoded.byteOffset, encoded.byteOffset + encoded.byteLength);

  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok,
      status,
      json: () => Promise.resolve(responseData),
      arrayBuffer: () => Promise.resolve(arrayBuffer),
      text: () => Promise.resolve(JSON.stringify(responseData)),
    })
  );

  return global.fetch;
};
