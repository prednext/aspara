import { describe, expect, test } from 'vitest';
import {
  buildExportFileName,
  calculateExportDimensions,
  generateCSVContent,
  getExportFileName,
  sanitizeFileName,
} from '../../src/aspara/dashboard/static/js/chart/export-utils.js';

describe('generateCSVContent', () => {
  test('generates correct CSV header', () => {
    const result = generateCSVContent([]);
    expect(result).toBe('series,step,value\n');
  });

  test('generates CSV for single series', () => {
    const series = [
      {
        name: 'loss',
        data: {
          steps: [0, 1, 2],
          values: [1.0, 0.5, 0.25],
        },
      },
    ];

    const result = generateCSVContent(series);
    expect(result).toContain('series,step,value\n');
    expect(result).toContain('"loss",0,1');
    expect(result).toContain('"loss",1,0.5');
    expect(result).toContain('"loss",2,0.25');
  });

  test('escapes double quotes in series name', () => {
    const series = [
      {
        name: 'metric"with"quotes',
        data: { steps: [0], values: [1.0] },
      },
    ];

    const result = generateCSVContent(series);
    expect(result).toContain('"metric""with""quotes"');
  });

  test('handles multiple series', () => {
    const series = [
      { name: 'loss', data: { steps: [0], values: [1.0] } },
      { name: 'accuracy', data: { steps: [0], values: [0.9] } },
    ];

    const result = generateCSVContent(series);
    expect(result).toContain('"loss"');
    expect(result).toContain('"accuracy"');
  });

  test('skips series with empty data', () => {
    const series = [
      { name: 'empty', data: { steps: [], values: [] } },
      { name: 'valid', data: { steps: [0], values: [1.0] } },
    ];

    const result = generateCSVContent(series);
    expect(result).not.toContain('empty');
    expect(result).toContain('valid');
  });

  test('skips series with null data', () => {
    const series = [
      { name: 'null', data: null },
      { name: 'valid', data: { steps: [0], values: [1.0] } },
    ];

    const result = generateCSVContent(series);
    expect(result).not.toContain('null');
    expect(result).toContain('valid');
  });

  test('handles numeric values correctly', () => {
    const series = [
      {
        name: 'test',
        data: {
          steps: [0, 1, 2, 3],
          values: [0, -1.5, 1e-10, 1000000],
        },
      },
    ];

    const result = generateCSVContent(series);
    expect(result).toContain('"test",0,0');
    expect(result).toContain('"test",1,-1.5');
    expect(result).toContain('"test",2,1e-10');
    expect(result).toContain('"test",3,1000000');
  });
});

describe('sanitizeFileName', () => {
  test('converts to lowercase', () => {
    expect(sanitizeFileName('TEST')).toBe('test');
    expect(sanitizeFileName('MixedCase')).toBe('mixedcase');
  });

  test('replaces special characters with underscore', () => {
    expect(sanitizeFileName('file/with:special*chars')).toBe('file_with_special_chars');
    expect(sanitizeFileName('test@file#name')).toBe('test_file_name');
  });

  test('replaces spaces with underscore', () => {
    expect(sanitizeFileName('my file name')).toBe('my_file_name');
  });

  test('preserves alphanumeric characters', () => {
    expect(sanitizeFileName('file123')).toBe('file123');
    expect(sanitizeFileName('abc123xyz')).toBe('abc123xyz');
  });

  test('handles empty string', () => {
    expect(sanitizeFileName('')).toBe('');
  });

  test('handles consecutive special characters', () => {
    expect(sanitizeFileName('a..b//c')).toBe('a__b__c');
  });
});

describe('getExportFileName', () => {
  test('uses title when available', () => {
    expect(getExportFileName({ title: 'My Chart', series: [] })).toBe('my_chart');
  });

  test('uses series name for single series without title', () => {
    expect(
      getExportFileName({
        series: [{ name: 'training_loss' }],
      })
    ).toBe('training_loss');
  });

  test('returns default for multiple series without title', () => {
    expect(
      getExportFileName({
        series: [{ name: 'a' }, { name: 'b' }],
      })
    ).toBe('chart');
  });

  test('returns default for empty series without title', () => {
    expect(getExportFileName({ series: [] })).toBe('chart');
  });

  test('returns default when no series', () => {
    expect(getExportFileName({})).toBe('chart');
  });

  test('sanitizes title', () => {
    expect(getExportFileName({ title: 'My Chart/v1.0' })).toBe('my_chart_v1_0');
  });

  test('sanitizes series name', () => {
    expect(
      getExportFileName({
        series: [{ name: 'train/loss' }],
      })
    ).toBe('train_loss');
  });
});

describe('calculateExportDimensions', () => {
  function createMockChart(zoomX, zoomY, width, height, margin) {
    return {
      zoom: { x: zoomX, y: zoomY },
      width,
      height,
      constructor: { MARGIN: margin },
    };
  }

  test('detects zoomed state when x is set', () => {
    const chart = createMockChart({ min: 0, max: 100 }, null, 600, 400, 60);
    const result = calculateExportDimensions(chart);

    expect(result.useZoomedArea).toBe(true);
  });

  test('detects zoomed state when y is set', () => {
    const chart = createMockChart(null, { min: 0, max: 10 }, 600, 400, 60);
    const result = calculateExportDimensions(chart);

    expect(result.useZoomedArea).toBe(true);
  });

  test('detects unzoomed state when both x and y are null', () => {
    const chart = createMockChart(null, null, 600, 400, 60);
    const result = calculateExportDimensions(chart);

    expect(result.useZoomedArea).toBe(false);
  });

  test('calculates correct dimensions', () => {
    const chart = createMockChart(null, null, 600, 400, 60);
    const result = calculateExportDimensions(chart);

    expect(result.margin).toBe(60);
    expect(result.plotWidth).toBe(480); // 600 - 60*2
    expect(result.plotHeight).toBe(280); // 400 - 60*2
  });

  test('handles different margin values', () => {
    const chart = createMockChart(null, null, 800, 600, 40);
    const result = calculateExportDimensions(chart);

    expect(result.margin).toBe(40);
    expect(result.plotWidth).toBe(720); // 800 - 40*2
    expect(result.plotHeight).toBe(520); // 600 - 40*2
  });
});

describe('buildExportFileName', () => {
  test('returns base name when not zoomed', () => {
    expect(buildExportFileName('chart', false)).toBe('chart');
    expect(buildExportFileName('my_chart', false)).toBe('my_chart');
  });

  test('adds zoomed suffix when zoomed', () => {
    expect(buildExportFileName('chart', true)).toBe('chart_zoomed');
    expect(buildExportFileName('my_chart', true)).toBe('my_chart_zoomed');
  });

  test('handles empty base name', () => {
    expect(buildExportFileName('', true)).toBe('_zoomed');
    expect(buildExportFileName('', false)).toBe('');
  });
});
