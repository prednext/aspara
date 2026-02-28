/**
 * Unit tests for SettingsMenu
 */

import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { SettingsMenu } from '../../src/aspara/dashboard/static/js/settings-menu.js';

describe('SettingsMenu', () => {
  let menu;

  function createDOM() {
    document.body.innerHTML = `
      <button id="settings-menu-button">Menu</button>
      <div id="settings-menu-dropdown" class="opacity-0 scale-95 pointer-events-none"></div>
      <input type="checkbox" id="fullWidthToggle" />
      <div id="main-content-container" class="max-w-7xl"></div>
      <div id="nav-container" class="max-w-7xl"></div>
    `;
  }

  beforeEach(() => {
    document.body.innerHTML = '';
    localStorage.clear();
  });

  afterEach(() => {
    if (menu) {
      menu.destroy();
      menu = null;
    }
  });

  describe('Constructor', () => {
    test('should initialize when required elements exist', () => {
      createDOM();
      menu = new SettingsMenu();

      expect(menu.menuButton).toBeTruthy();
      expect(menu.menuDropdown).toBeTruthy();
      expect(menu.isOpen).toBe(false);
    });

    test('should return early when menu button is missing', () => {
      document.body.innerHTML = '<div id="settings-menu-dropdown"></div>';
      menu = new SettingsMenu();

      expect(menu.isOpen).toBeUndefined();
    });

    test('should return early when menu dropdown is missing', () => {
      document.body.innerHTML = '<button id="settings-menu-button"></button>';
      menu = new SettingsMenu();

      expect(menu.isOpen).toBeUndefined();
    });
  });

  describe('toggleMenu', () => {
    test('should open menu when closed', () => {
      createDOM();
      menu = new SettingsMenu();

      menu.toggleMenu();

      expect(menu.isOpen).toBe(true);
      expect(menu.menuDropdown.classList.contains('opacity-100')).toBe(true);
      expect(menu.menuDropdown.classList.contains('scale-100')).toBe(true);
    });

    test('should close menu when open', () => {
      createDOM();
      menu = new SettingsMenu();

      menu.openMenu();
      menu.toggleMenu();

      expect(menu.isOpen).toBe(false);
      expect(menu.menuDropdown.classList.contains('opacity-0')).toBe(true);
      expect(menu.menuDropdown.classList.contains('pointer-events-none')).toBe(true);
    });
  });

  describe('openMenu', () => {
    test('should add visible classes and remove hidden classes', () => {
      createDOM();
      menu = new SettingsMenu();

      menu.openMenu();

      expect(menu.menuDropdown.classList.contains('opacity-100')).toBe(true);
      expect(menu.menuDropdown.classList.contains('scale-100')).toBe(true);
      expect(menu.menuDropdown.classList.contains('opacity-0')).toBe(false);
      expect(menu.menuDropdown.classList.contains('scale-95')).toBe(false);
      expect(menu.menuDropdown.classList.contains('pointer-events-none')).toBe(false);
    });
  });

  describe('closeMenu', () => {
    test('should add hidden classes and remove visible classes', () => {
      createDOM();
      menu = new SettingsMenu();

      menu.openMenu();
      menu.closeMenu();

      expect(menu.menuDropdown.classList.contains('opacity-0')).toBe(true);
      expect(menu.menuDropdown.classList.contains('scale-95')).toBe(true);
      expect(menu.menuDropdown.classList.contains('pointer-events-none')).toBe(true);
      expect(menu.menuDropdown.classList.contains('opacity-100')).toBe(false);
      expect(menu.menuDropdown.classList.contains('scale-100')).toBe(false);
    });
  });

  describe('Event listeners', () => {
    test('should toggle menu on button click', () => {
      createDOM();
      menu = new SettingsMenu();

      menu.menuButton.click();
      expect(menu.isOpen).toBe(true);

      menu.menuButton.click();
      expect(menu.isOpen).toBe(false);
    });

    test('should close menu on outside click', () => {
      createDOM();
      menu = new SettingsMenu();

      menu.openMenu();
      document.dispatchEvent(new Event('click'));

      expect(menu.isOpen).toBe(false);
    });

    test('should not close menu when clicking inside dropdown', () => {
      createDOM();
      menu = new SettingsMenu();

      menu.openMenu();
      const event = new Event('click', { bubbles: true });
      Object.defineProperty(event, 'target', { value: menu.menuDropdown });
      document.dispatchEvent(event);

      expect(menu.isOpen).toBe(true);
    });

    test('should close menu on Escape key', () => {
      createDOM();
      menu = new SettingsMenu();

      menu.openMenu();
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));

      expect(menu.isOpen).toBe(false);
    });

    test('should not close menu on other keys', () => {
      createDOM();
      menu = new SettingsMenu();

      menu.openMenu();
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));

      expect(menu.isOpen).toBe(true);
    });
  });

  describe('Full width toggle', () => {
    test('should enable full width on toggle', () => {
      createDOM();
      menu = new SettingsMenu();

      menu.fullWidthToggle.checked = true;
      menu.fullWidthToggle.dispatchEvent(new Event('change'));

      expect(localStorage.getItem('aspara-full-width')).toBe('true');
      expect(menu.mainContainer.classList.contains('max-w-full')).toBe(true);
      expect(menu.mainContainer.classList.contains('px-8')).toBe(true);
      expect(menu.navContainer.classList.contains('max-w-full')).toBe(true);
    });

    test('should disable full width on toggle off', () => {
      createDOM();
      menu = new SettingsMenu();

      // Enable first
      menu.fullWidthToggle.checked = true;
      menu.fullWidthToggle.dispatchEvent(new Event('change'));

      // Then disable
      menu.fullWidthToggle.checked = false;
      menu.fullWidthToggle.dispatchEvent(new Event('change'));

      expect(localStorage.getItem('aspara-full-width')).toBe('false');
      expect(menu.mainContainer.classList.contains('max-w-7xl')).toBe(true);
      expect(menu.mainContainer.classList.contains('max-w-full')).toBe(false);
    });

    test('should dispatch fullWidthChanged event', () => {
      createDOM();
      menu = new SettingsMenu();

      const handler = vi.fn();
      window.addEventListener('fullWidthChanged', handler);

      menu.fullWidthToggle.checked = true;
      menu.fullWidthToggle.dispatchEvent(new Event('change'));

      expect(handler).toHaveBeenCalledTimes(1);
      expect(handler.mock.calls[0][0].detail).toEqual({ enabled: true });

      window.removeEventListener('fullWidthChanged', handler);
    });

    test('should close menu after toggle', () => {
      createDOM();
      menu = new SettingsMenu();

      menu.openMenu();
      menu.fullWidthToggle.checked = true;
      menu.fullWidthToggle.dispatchEvent(new Event('change'));

      expect(menu.isOpen).toBe(false);
    });
  });

  describe('restoreSettings', () => {
    test('should restore full width from localStorage', () => {
      localStorage.setItem('aspara-full-width', 'true');
      createDOM();
      menu = new SettingsMenu();

      expect(menu.fullWidthToggle.checked).toBe(true);
      expect(menu.mainContainer.classList.contains('max-w-full')).toBe(true);
      expect(menu.navContainer.classList.contains('max-w-full')).toBe(true);
    });

    test('should not enable full width when not stored', () => {
      createDOM();
      menu = new SettingsMenu();

      expect(menu.fullWidthToggle.checked).toBe(false);
      expect(menu.mainContainer.classList.contains('max-w-7xl')).toBe(true);
    });
  });

  describe('enableFullWidth / disableFullWidth', () => {
    test('should handle missing mainContainer', () => {
      document.body.innerHTML = `
        <button id="settings-menu-button">Menu</button>
        <div id="settings-menu-dropdown" class="opacity-0 scale-95 pointer-events-none"></div>
        <input type="checkbox" id="fullWidthToggle" />
      `;
      menu = new SettingsMenu();

      // Should not throw
      expect(() => menu.enableFullWidth()).not.toThrow();
      expect(() => menu.disableFullWidth()).not.toThrow();
    });
  });

  describe('destroy', () => {
    test('should remove document event listeners', () => {
      createDOM();
      menu = new SettingsMenu();

      expect(menu.documentClickHandler).not.toBeNull();
      expect(menu.documentKeydownHandler).not.toBeNull();

      menu.destroy();

      expect(menu.documentClickHandler).toBeNull();
      expect(menu.documentKeydownHandler).toBeNull();
    });

    test('should be safe to call twice', () => {
      createDOM();
      menu = new SettingsMenu();

      menu.destroy();
      expect(() => menu.destroy()).not.toThrow();
    });
  });

  describe('Constructor without fullWidthToggle', () => {
    test('should work without fullWidthToggle element', () => {
      document.body.innerHTML = `
        <button id="settings-menu-button">Menu</button>
        <div id="settings-menu-dropdown" class="opacity-0 scale-95 pointer-events-none"></div>
      `;
      menu = new SettingsMenu();

      expect(menu.fullWidthToggle).toBeNull();
      expect(menu.isOpen).toBe(false);
    });
  });
});
