import { beforeEach, describe, expect, test, vi } from 'vitest';
import { getNotificationIcon, getNotificationStyles } from '../../src/aspara/dashboard/static/js/notifications.js';

describe('Notification Pure Functions', () => {
  describe('getNotificationStyles', () => {
    test('returns correct styles for success type', () => {
      const result = getNotificationStyles('success');
      expect(result).toContain('bg-green-50');
      expect(result).toContain('text-green-800');
      expect(result).toContain('border-green-200');
    });

    test('returns correct styles for error type', () => {
      const result = getNotificationStyles('error');
      expect(result).toContain('bg-red-50');
      expect(result).toContain('text-red-800');
      expect(result).toContain('border-red-200');
    });

    test('returns correct styles for warning type', () => {
      const result = getNotificationStyles('warning');
      expect(result).toContain('bg-yellow-50');
      expect(result).toContain('text-yellow-800');
      expect(result).toContain('border-yellow-200');
    });

    test('returns info styles for info type', () => {
      const result = getNotificationStyles('info');
      expect(result).toContain('bg-blue-50');
      expect(result).toContain('text-blue-800');
      expect(result).toContain('border-blue-200');
    });

    test('returns info styles as default for unknown type', () => {
      const result = getNotificationStyles('unknown');
      expect(result).toContain('bg-blue-50');
      expect(result).toContain('text-blue-800');
    });

    test('returns info styles for undefined type', () => {
      const result = getNotificationStyles(undefined);
      expect(result).toContain('bg-blue-50');
    });
  });

  describe('getNotificationIcon', () => {
    test('returns SVG for success type', () => {
      const icon = getNotificationIcon('success');
      expect(icon).toContain('<svg');
      expect(icon).toContain('</svg>');
      expect(icon).toContain('text-green-400');
      expect(icon).toContain('M5 13l4 4L19 7');
    });

    test('returns SVG for error type', () => {
      const icon = getNotificationIcon('error');
      expect(icon).toContain('<svg');
      expect(icon).toContain('text-red-400');
      expect(icon).toContain('M12 8v4m0 4h.01');
    });

    test('returns SVG for warning type', () => {
      const icon = getNotificationIcon('warning');
      expect(icon).toContain('<svg');
      expect(icon).toContain('text-yellow-400');
      expect(icon).toContain('M12 9v2m0 4h.01');
    });

    test('returns SVG for info type', () => {
      const icon = getNotificationIcon('info');
      expect(icon).toContain('<svg');
      expect(icon).toContain('text-blue-400');
      expect(icon).toContain('M13 16h-1v-4h-1');
    });

    test('returns different icons for each type', () => {
      const types = ['success', 'error', 'warning', 'info'];
      const icons = types.map(getNotificationIcon);
      const uniqueIcons = new Set(icons);
      expect(uniqueIcons.size).toBe(4);
    });

    test('returns info icon as default for unknown type', () => {
      const icon = getNotificationIcon('unknown');
      expect(icon).toContain('text-blue-400');
      expect(icon).toContain('M13 16h-1v-4h-1');
    });

    test('all icons have proper SVG structure', () => {
      const types = ['success', 'error', 'warning', 'info'];
      for (const type of types) {
        const icon = getNotificationIcon(type);
        expect(icon).toContain('class="w-4 h-4');
        expect(icon).toContain('viewBox="0 0 24 24"');
        expect(icon).toContain('fill="none"');
        expect(icon).toContain('stroke="currentColor"');
      }
    });
  });
});
