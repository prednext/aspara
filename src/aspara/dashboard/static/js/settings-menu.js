/**
 * Settings Menu JavaScript module
 * Handles hamburger menu interactions and settings toggles
 */

const FULL_WIDTH_KEY = 'aspara-full-width';

class SettingsMenu {
  constructor() {
    this.menuButton = document.getElementById('settings-menu-button');
    this.menuDropdown = document.getElementById('settings-menu-dropdown');
    this.fullWidthToggle = document.getElementById('fullWidthToggle');
    this.mainContainer = document.getElementById('main-content-container');
    this.navContainer = document.getElementById('nav-container');

    if (!this.menuButton || !this.menuDropdown) {
      return;
    }

    this.isOpen = false;

    // Document event handlers (stored for cleanup)
    this.documentClickHandler = null;
    this.documentKeydownHandler = null;

    this.setupEventListeners();
    this.restoreSettings();
  }

  setupEventListeners() {
    // Toggle menu on button click
    this.menuButton.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleMenu();
    });

    // Close menu when clicking outside (stored for cleanup)
    this.documentClickHandler = (e) => {
      if (this.isOpen && !this.menuDropdown.contains(e.target)) {
        this.closeMenu();
      }
    };
    document.addEventListener('click', this.documentClickHandler);

    // Close menu on Escape key (stored for cleanup)
    this.documentKeydownHandler = (e) => {
      if (e.key === 'Escape' && this.isOpen) {
        this.closeMenu();
      }
    };
    document.addEventListener('keydown', this.documentKeydownHandler);

    // Full Width toggle
    if (this.fullWidthToggle) {
      this.fullWidthToggle.addEventListener('change', () => {
        this.handleFullWidthToggle();
      });
    }
  }

  toggleMenu() {
    if (this.isOpen) {
      this.closeMenu();
    } else {
      this.openMenu();
    }
  }

  openMenu() {
    this.menuDropdown.classList.remove('opacity-0', 'scale-95', 'pointer-events-none');
    this.menuDropdown.classList.add('opacity-100', 'scale-100');
    this.isOpen = true;
  }

  closeMenu() {
    this.menuDropdown.classList.remove('opacity-100', 'scale-100');
    this.menuDropdown.classList.add('opacity-0', 'scale-95', 'pointer-events-none');
    this.isOpen = false;
  }

  restoreSettings() {
    // Restore Full Width setting
    const isFullWidth = localStorage.getItem(FULL_WIDTH_KEY) === 'true';
    if (this.fullWidthToggle) {
      this.fullWidthToggle.checked = isFullWidth;
    }
    if (isFullWidth) {
      this.enableFullWidth();
    }
  }

  handleFullWidthToggle() {
    const isEnabled = this.fullWidthToggle.checked;
    localStorage.setItem(FULL_WIDTH_KEY, isEnabled);

    if (isEnabled) {
      this.enableFullWidth();
    } else {
      this.disableFullWidth();
    }

    // Dispatch custom event for other modules to listen to
    window.dispatchEvent(
      new CustomEvent('fullWidthChanged', {
        detail: { enabled: isEnabled },
      })
    );

    // Close menu after toggle
    this.closeMenu();
  }

  enableFullWidth() {
    if (this.mainContainer) {
      this.mainContainer.classList.remove('max-w-7xl');
      this.mainContainer.classList.add('max-w-full', 'px-8');
    }
    if (this.navContainer) {
      this.navContainer.classList.remove('max-w-7xl');
      this.navContainer.classList.add('max-w-full', 'px-8');
    }
  }

  disableFullWidth() {
    if (this.mainContainer) {
      this.mainContainer.classList.remove('max-w-full', 'px-8');
      this.mainContainer.classList.add('max-w-7xl');
    }
    if (this.navContainer) {
      this.navContainer.classList.remove('max-w-full', 'px-8');
      this.navContainer.classList.add('max-w-7xl');
    }
  }

  /**
   * Clean up event listeners.
   */
  destroy() {
    if (this.documentClickHandler) {
      document.removeEventListener('click', this.documentClickHandler);
      this.documentClickHandler = null;
    }
    if (this.documentKeydownHandler) {
      document.removeEventListener('keydown', this.documentKeydownHandler);
      this.documentKeydownHandler = null;
    }
  }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  new SettingsMenu();
});

export { SettingsMenu };
