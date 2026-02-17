/**
 * ChartColorPalette の色パレット・RunStyleRegistryのテスト
 */

import { beforeEach, describe, expect, test } from 'vitest';
import { ChartColorPalette } from '../../src/aspara/dashboard/static/js/chart/color-palette.js';

describe('ChartColorPalette', () => {
  let palette;

  beforeEach(() => {
    palette = new ChartColorPalette();
  });

  describe('Base Color Palette', () => {
    test('should have 16 base colors', () => {
      expect(palette.baseColors).toBeDefined();
      expect(palette.baseColors.length).toBe(16);
    });

    test('all base colors should be valid hex colors', () => {
      const hexPattern = /^#[0-9A-F]{6}$/i;
      for (const color of palette.baseColors) {
        expect(color).toMatch(hexPattern);
      }
    });
  });

  describe('Border Dash Patterns', () => {
    test('should have 4 border dash patterns', () => {
      expect(palette.borderDashPatterns).toBeDefined();
      expect(palette.borderDashPatterns.length).toBe(4);
    });

    test('first pattern should be solid (empty array)', () => {
      expect(palette.borderDashPatterns[0]).toEqual([]);
    });
  });

  describe('Color Conversion Functions', () => {
    test('hexToRgb should convert hex to RGB correctly', () => {
      const rgb = palette.hexToRgb('#2563EB');
      expect(rgb).toEqual({ r: 37, g: 99, b: 235 });
    });

    test('rgbToHsl should convert RGB to HSL correctly', () => {
      const hsl = palette.rgbToHsl(37, 99, 235);
      expect(hsl.h).toBeCloseTo(221, 0);
      expect(hsl.s).toBeGreaterThan(0);
      expect(hsl.l).toBeGreaterThan(0);
    });

    test('hslToString should format HSL correctly', () => {
      const hsl = { h: 217.5, s: 85.3, l: 53.2 };
      const result = palette.hslToString(hsl);
      expect(result).toBe('hsl(218, 85%, 53%)');
    });
  });

  describe('Variant Application', () => {
    test('variant 0 (normal) should not change S/L', () => {
      const hsl = { h: 200, s: 70, l: 50 };
      const result = palette.applyVariant(hsl, 0);
      expect(result.s).toBe(70);
      expect(result.l).toBe(50);
    });

    test('variant 1 (muted) should decrease S and L', () => {
      const hsl = { h: 200, s: 70, l: 50 };
      const result = palette.applyVariant(hsl, 1);
      expect(result.s).toBe(55); // 70 - 15
      expect(result.l).toBe(44); // 50 - 6
    });

    test('variant 2 (bright) should increase S and L', () => {
      const hsl = { h: 200, s: 70, l: 50 };
      const result = palette.applyVariant(hsl, 2);
      expect(result.s).toBe(78); // 70 + 8
      expect(result.l).toBe(56); // 50 + 6
    });

    test('should clamp S to safe range (35-95)', () => {
      const lowHsl = { h: 200, s: 30, l: 50 };
      const lowResult = palette.applyVariant(lowHsl, 1); // Would be 15
      expect(lowResult.s).toBeGreaterThanOrEqual(35);

      const highHsl = { h: 200, s: 90, l: 50 };
      const highResult = palette.applyVariant(highHsl, 2); // Would be 98
      expect(highResult.s).toBeLessThanOrEqual(95);
    });

    test('should clamp L to safe range (30-70)', () => {
      const lowHsl = { h: 200, s: 70, l: 35 };
      const lowResult = palette.applyVariant(lowHsl, 1); // Would be 29
      expect(lowResult.l).toBeGreaterThanOrEqual(30);

      const highHsl = { h: 200, s: 70, l: 65 };
      const highResult = palette.applyVariant(highHsl, 2); // Would be 71
      expect(highResult.l).toBeLessThanOrEqual(70);
    });
  });

  describe('Style Generation', () => {
    test('should generate valid style object', () => {
      const style = palette.generateStyle(0);
      expect(style).toHaveProperty('borderColor');
      expect(style).toHaveProperty('backgroundColor');
      expect(style).toHaveProperty('borderDash');
      expect(Array.isArray(style.borderDash)).toBe(true);
    });

    test('first 16 styles should use different base colors', () => {
      const colors = new Set();
      for (let i = 0; i < 16; i++) {
        const style = palette.generateStyle(i);
        colors.add(style.borderColor);
      }
      // Should have 16 unique colors
      expect(colors.size).toBe(16);
    });

    test('first 16 styles should all use solid line (no dash)', () => {
      for (let i = 0; i < 16; i++) {
        const style = palette.generateStyle(i);
        expect(style.borderDash).toEqual([]);
      }
    });

    test('styles 16-31 should use variants (different S/L)', () => {
      const style0 = palette.generateStyle(0);
      const style16 = palette.generateStyle(16);

      // Same base color but different variant
      expect(style0.borderColor).not.toBe(style16.borderColor);
      expect(style16.borderDash).toEqual([]); // Still solid
    });

    test('styles 48+ should use different dash patterns', () => {
      const style48 = palette.generateStyle(48);
      expect(style48.borderDash).not.toEqual([]);
    });
  });

  describe('RunStyleRegistry', () => {
    test('should initialize with empty registry', () => {
      expect(palette.runStyleRegistry.size).toBe(0);
      expect(palette.nextStyleIndex).toBe(0);
    });

    test('ensureRunStyles should assign styles to runs', () => {
      const runIds = ['run1', 'run2', 'run3'];
      palette.ensureRunStyles(runIds);

      expect(palette.runStyleRegistry.size).toBe(3);
      expect(palette.nextStyleIndex).toBe(3);
    });

    test('ensureRunStyles should maintain stable assignment', () => {
      const runIds = ['run1', 'run2', 'run3'];
      palette.ensureRunStyles(runIds);

      const style1 = palette.getRunStyle('run1');
      const style2 = palette.getRunStyle('run2');

      // Call again - should not change
      palette.ensureRunStyles(runIds);

      expect(palette.getRunStyle('run1')).toEqual(style1);
      expect(palette.getRunStyle('run2')).toEqual(style2);
      expect(palette.nextStyleIndex).toBe(3); // Should not increment
    });

    test('ensureRunStyles should sort runs for stable ordering', () => {
      // Different order
      palette.ensureRunStyles(['run3', 'run1', 'run2']);
      const style1a = palette.getRunStyle('run1');

      // Reset
      palette.reset();

      // Same runs, different order
      palette.ensureRunStyles(['run2', 'run3', 'run1']);
      const style1b = palette.getRunStyle('run1');

      // Should get same style due to sorting
      expect(style1a).toEqual(style1b);
    });

    test('ensureRunStyles should handle duplicate run IDs', () => {
      const runIds = ['run1', 'run2', 'run1', 'run2'];
      palette.ensureRunStyles(runIds);

      expect(palette.runStyleRegistry.size).toBe(2);
      expect(palette.nextStyleIndex).toBe(2);
    });

    test('getRunStyle should return assigned style', () => {
      palette.ensureRunStyles(['run1']);
      const style = palette.getRunStyle('run1');

      expect(style).toBeDefined();
      expect(style.borderColor).toBeDefined();
    });

    test('getRunStyle should return fallback for unknown run', () => {
      const style = palette.getRunStyle('unknown_run');
      expect(style).toBeDefined();
      expect(style.borderColor).toBeDefined();
    });
  });

  describe('AC 1: 16 runs should have different colors', () => {
    test('16 runs should produce 16 unique colors', () => {
      const runIds = Array.from({ length: 16 }, (_, i) => `run${i}`);
      palette.ensureRunStyles(runIds);

      const colors = new Set();
      for (const runId of runIds) {
        const style = palette.getRunStyle(runId);
        colors.add(style.borderColor);
      }

      expect(colors.size).toBe(16);
    });
  });

  describe('AC 2: 48 runs should have sufficient color variation', () => {
    test('48 runs should produce many unique color combinations', () => {
      const runIds = Array.from({ length: 48 }, (_, i) => `run${i}`);
      palette.ensureRunStyles(runIds);

      const colorVariants = new Set();
      for (const runId of runIds) {
        const style = palette.getRunStyle(runId);
        colorVariants.add(style.borderColor);
      }

      // Should have close to 16 * 3 = 48 unique color variants
      // (some may overlap due to saturation clamping)
      expect(colorVariants.size).toBeGreaterThanOrEqual(47);
    });
  });

  describe('AC 3: Many runs should use dash patterns', () => {
    test('60 runs should include different dash patterns', () => {
      const runIds = Array.from({ length: 60 }, (_, i) => `run${i}`);
      palette.ensureRunStyles(runIds);

      const styleSignatures = new Set();
      for (const runId of runIds) {
        const style = palette.getRunStyle(runId);
        const signature = `${style.borderColor}|${JSON.stringify(style.borderDash)}`;
        styleSignatures.add(signature);
      }

      // Should have more unique combinations due to dash patterns
      expect(styleSignatures.size).toBeGreaterThan(48);
    });

    test('runs beyond 48 should have non-empty dash patterns', () => {
      const runIds = Array.from({ length: 60 }, (_, i) => `run${i}`);
      palette.ensureRunStyles(runIds);

      // Check that at least some runs beyond index 48 have dash patterns
      let dashCount = 0;
      for (let i = 48; i < 60; i++) {
        const style = palette.getRunStyle(`run${i}`);
        if (style.borderDash.length > 0) {
          dashCount++;
        }
      }
      expect(dashCount).toBeGreaterThan(0);
    });
  });

  describe('AC 4: Same run has same style across metrics', () => {
    test('same run should get consistent style', () => {
      // Simulate multiple metric charts
      palette.ensureRunStyles(['run1', 'run2']);
      const style1a = palette.getRunStyle('run1');
      const style2a = palette.getRunStyle('run2');

      // Get again (as if from different metric chart)
      const style1b = palette.getRunStyle('run1');
      const style2b = palette.getRunStyle('run2');

      expect(style1a).toEqual(style1b);
      expect(style2a).toEqual(style2b);
    });
  });
});
