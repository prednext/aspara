import { CHART_CONTROL_LABELS, ICON_DOWNLOAD, ICON_FULLSCREEN, ICON_HELP, ICON_RESET_ZOOM } from '../html-utils.js';

/**
 * Apply shared styling and ARIA attributes to a chart control button.
 * @param {HTMLButtonElement} button
 * @param {string} label - Accessible name (also used as tooltip)
 */
function styleControlButton(button, label) {
  button.type = 'button';
  button.setAttribute('aria-label', label);
  button.title = label;
  button.style.cssText = `
        width: 32px;
        height: 32px;
        border: 1px solid #ddd;
        background: white;
        cursor: pointer;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #555;
    `;
}

export class ChartControls {
  constructor(chart, chartExport) {
    this.chart = chart;
    this.chartExport = chartExport;
    this.buttonContainer = null;
    this.resetButton = null;
    this.fullSizeButton = null;
    this.downloadButton = null;
    this.downloadMenu = null;
    this.helpButton = null;
    this.helpPopover = null;
    this.logScaleControl = null;
    this.logScaleCheckbox = null;

    // Document click handler (stored for cleanup)
    this.documentClickHandler = null;
    // fullscreenchange handler (stored for cleanup)
    this.fullscreenChangeHandler = null;
    // Keydown handler for Esc / arrow keys inside open menus (stored for cleanup)
    this._menuKeydownHandler = null;
  }

  create() {
    this.chart.container.style.position = 'relative';

    this.buttonContainer = document.createElement('div');
    this.buttonContainer.style.cssText = `
            position: absolute;
            top: 10px;
            right: 10px;
            display: flex;
            gap: 8px;
            z-index: 10;
        `;

    this.createLogScaleControl();
    this.createResetButton();
    this.createFullSizeButton();
    this.createDownloadButton();
    this.createHelpButton();

    this.buttonContainer.appendChild(this.logScaleControl);
    this.buttonContainer.appendChild(this.resetButton);
    this.buttonContainer.appendChild(this.fullSizeButton);
    this.buttonContainer.appendChild(this.downloadButton);
    this.buttonContainer.appendChild(this.helpButton);
    this.chart.container.appendChild(this.buttonContainer);

    this.updateLogScaleControl();
    // Wire up callback so the checkbox reflects scale changes from other sources
    // (e.g. keyboard shortcuts) without coupling Chart to ChartControls.
    const existingYScaleCallback = this.chart.onYScaleChange;
    this.chart.onYScaleChange = (scale) => {
      if (existingYScaleCallback) existingYScaleCallback(scale);
      this.updateLogScaleControl();
    };
  }

  createResetButton() {
    this.resetButton = document.createElement('button');
    this.resetButton.innerHTML = ICON_RESET_ZOOM;
    styleControlButton(this.resetButton, CHART_CONTROL_LABELS.resetZoom);

    this.attachButtonHover(this.resetButton);
    this.resetButton.addEventListener('click', () => this.chart.resetZoom());
  }

  createFullSizeButton() {
    this.fullSizeButton = document.createElement('button');
    this.fullSizeButton.innerHTML = ICON_FULLSCREEN;
    styleControlButton(this.fullSizeButton, CHART_CONTROL_LABELS.enterFullscreen);

    this.attachButtonHover(this.fullSizeButton);
    this.fullSizeButton.addEventListener('click', () => this.fitToFullSize());

    // Keep the title/aria-label in sync with the actual fullscreen state so
    // the tooltip reflects what clicking the button will do (e.g. after the
    // user exits fullscreen via Esc).
    this.fullscreenChangeHandler = () => {
      if (!this.fullSizeButton) return;
      const label = document.fullscreenElement
        ? CHART_CONTROL_LABELS.exitFullscreen
        : CHART_CONTROL_LABELS.enterFullscreen;
      this.fullSizeButton.title = label;
      this.fullSizeButton.setAttribute('aria-label', label);
    };
    document.addEventListener('fullscreenchange', this.fullscreenChangeHandler);
  }

  createDownloadButton() {
    this.downloadButton = document.createElement('button');
    this.downloadButton.innerHTML = ICON_DOWNLOAD;
    styleControlButton(this.downloadButton, CHART_CONTROL_LABELS.download);
    this.downloadButton.style.position = 'relative';
    // Declare the popup menu relationship for AT users.
    this.downloadButton.setAttribute('aria-haspopup', 'menu');
    this.downloadButton.setAttribute('aria-expanded', 'false');

    this.downloadMenu = document.createElement('div');
    this.downloadMenu.setAttribute('role', 'menu');
    this.downloadMenu.style.cssText = `
            position: absolute;
            top: 100%;
            right: 0;
            background: white;
            border: 1px solid #ddd;
            border-radius: 6px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            display: none;
            flex-direction: column;
            width: 120px;
            z-index: 20;
        `;

    const downloadOptions = [
      { format: 'CSV', label: 'CSV format' },
      { format: 'SVG', label: 'SVG image' },
      { format: 'PNG', label: 'PNG image' },
    ];

    for (const option of downloadOptions) {
      const menuItem = document.createElement('button');
      menuItem.textContent = option.label;
      menuItem.setAttribute('role', 'menuitem');
      menuItem.style.cssText = `
                padding: 8px 12px;
                text-align: left;
                background: none;
                border: none;
                cursor: pointer;
                font-size: 13px;
                color: #333;
            `;
      menuItem.addEventListener('mouseenter', () => {
        menuItem.style.background = '#f5f5f5';
      });
      menuItem.addEventListener('mouseleave', () => {
        menuItem.style.background = 'none';
      });
      menuItem.addEventListener('click', (e) => {
        e.stopPropagation();
        this.chartExport.downloadData(option.format);
        this.toggleDownloadMenu(false);
      });
      this.downloadMenu.appendChild(menuItem);
    }

    this.downloadButton.appendChild(this.downloadMenu);

    this.attachButtonHover(this.downloadButton);
    this.downloadButton.addEventListener('click', () => this.toggleDownloadMenu());
  }

  createLogScaleControl() {
    const controlId = `logscale-${Math.random().toString(36).slice(2, 9)}`;

    this.logScaleControl = document.createElement('label');
    this.logScaleControl.htmlFor = controlId;
    this.logScaleControl.style.cssText = `
            height: 32px;
            border: 1px solid #ddd;
            background: white;
            border-radius: 6px;
            display: flex;
            align-items: center;
            padding: 0 10px;
            gap: 6px;
            font-size: 12px;
            color: #555;
            cursor: pointer;
            user-select: none;
        `;

    this.logScaleCheckbox = document.createElement('input');
    this.logScaleCheckbox.type = 'checkbox';
    this.logScaleCheckbox.id = controlId;
    this.logScaleCheckbox.setAttribute('aria-label', CHART_CONTROL_LABELS.toggleLogScale);
    this.logScaleCheckbox.style.cursor = 'pointer';

    const labelText = document.createElement('span');
    labelText.textContent = 'logscale';

    this.logScaleControl.appendChild(this.logScaleCheckbox);
    this.logScaleControl.appendChild(labelText);

    this.logScaleControl.addEventListener('mouseenter', () => {
      this.logScaleControl.style.background = '#f5f5f5';
      this.logScaleControl.style.borderColor = '#bbb';
    });
    this.logScaleControl.addEventListener('mouseleave', () => {
      this.logScaleControl.style.background = 'white';
      this.logScaleControl.style.borderColor = '#ddd';
    });

    this.logScaleCheckbox.addEventListener('change', () => {
      this.chart.toggleYScale();
    });
  }

  updateLogScaleControl() {
    if (!this.logScaleCheckbox) return;
    const isLog = this.chart.yScale === 'log';
    this.logScaleCheckbox.checked = isLog;
  }

  createHelpButton() {
    this.helpButton = document.createElement('button');
    this.helpButton.innerHTML = ICON_HELP;
    styleControlButton(this.helpButton, CHART_CONTROL_LABELS.help);
    this.helpButton.style.position = 'relative';
    // The help popover is informational, not a menu, but it is a popup.
    this.helpButton.setAttribute('aria-haspopup', 'dialog');
    this.helpButton.setAttribute('aria-expanded', 'false');

    this.helpPopover = document.createElement('div');
    this.helpPopover.setAttribute('role', 'dialog');
    this.helpPopover.style.cssText = `
            position: absolute;
            top: 100%;
            right: 0;
            background: white;
            border: 1px solid #ddd;
            border-radius: 6px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            display: none;
            flex-direction: column;
            width: 220px;
            z-index: 20;
            padding: 10px 12px;
        `;

    // SSOT: chart interaction descriptions live here. Each button's
    // `title` attribute stays short; this popover is the canonical place
    // for the full explanation.
    const items = [
      { icon: '✋', text: 'Drag on chart to zoom' },
      { icon: '↺', text: 'Click reset to restore view' },
      { icon: '⛶', text: 'Click fullscreen to expand' },
      { icon: '⤓', text: 'Click download to export data' },
      { icon: 'log', text: 'Check logscale to toggle y-axis scale' },
    ];

    for (const item of items) {
      const row = document.createElement('div');
      row.style.cssText = `
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 4px 0;
                font-size: 13px;
                color: #333;
            `;
      const iconSpan = document.createElement('span');
      iconSpan.textContent = item.icon;
      iconSpan.setAttribute('aria-hidden', 'true');
      iconSpan.style.cssText = 'width: 18px; text-align: center; flex-shrink: 0;';
      const textSpan = document.createElement('span');
      textSpan.textContent = item.text;
      row.appendChild(iconSpan);
      row.appendChild(textSpan);
      this.helpPopover.appendChild(row);
    }

    this.helpButton.appendChild(this.helpPopover);

    this.attachButtonHover(this.helpButton);
    this.helpButton.addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleHelpPopover();
    });

    // Reuse the document click handler pattern from the download menu to
    // close the help popover when clicking outside.
    const existingHandler = this.documentClickHandler;
    this.documentClickHandler = (e) => {
      if (this.downloadButton && !this.downloadButton.contains(e.target)) {
        this.toggleDownloadMenu(false);
      }
      if (this.helpButton && !this.helpButton.contains(e.target)) {
        this.toggleHelpPopover(false);
      }
    };
    // Replace the previously registered handler (if any) with the unified one.
    if (existingHandler) {
      document.removeEventListener('click', existingHandler);
    }
    document.addEventListener('click', this.documentClickHandler);

    // Global keydown handler: Esc closes the open popup and returns focus
    // to the triggering button; arrow keys move between menu items of the
    // download menu (ARIA Authoring Practices menu pattern).
    this._menuKeydownHandler = (e) => this._handleMenuKeydown(e);
    document.addEventListener('keydown', this._menuKeydownHandler);
  }

  /**
   * Handle keyboard navigation for open popups (Esc / Arrow / Home / End).
   * Follows the ARIA Authoring Practices Guide menu pattern.
   */
  _handleMenuKeydown(e) {
    const downloadOpen = this.downloadMenu?.style.display === 'flex';
    const helpOpen = this.helpPopover?.style.display === 'flex';
    if (!downloadOpen && !helpOpen) return;

    // Esc closes whichever popup is open and returns focus to its trigger.
    if (e.key === 'Escape') {
      e.preventDefault();
      if (downloadOpen) {
        this.toggleDownloadMenu(false);
        this.downloadButton?.focus();
      } else if (helpOpen) {
        this.toggleHelpPopover(false);
        this.helpButton?.focus();
      }
      return;
    }

    // Arrow / Home / End only apply to the download menu (role=menu).
    if (!downloadOpen) return;

    const items = Array.from(this.downloadMenu.querySelectorAll('[role="menuitem"]'));
    if (items.length === 0) return;
    const currentIndex = items.indexOf(document.activeElement);

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      items[(currentIndex + 1) % items.length].focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      items[(currentIndex - 1 + items.length) % items.length].focus();
    } else if (e.key === 'Home') {
      e.preventDefault();
      items[0].focus();
    } else if (e.key === 'End') {
      e.preventDefault();
      items[items.length - 1].focus();
    }
  }

  toggleHelpPopover(forceState) {
    if (!this.helpPopover) return;
    const isVisible = this.helpPopover.style.display === 'flex';
    const newState = forceState !== undefined ? forceState : !isVisible;
    this.helpPopover.style.display = newState ? 'flex' : 'none';
    if (this.helpButton) {
      this.helpButton.setAttribute('aria-expanded', newState ? 'true' : 'false');
    }
    if (newState) {
      // Move focus into the dialog so AT users perceive the context switch.
      this.helpPopover.focus?.();
    }
  }

  fitToFullSize() {
    if (!document.fullscreenElement) {
      if (this.chart.container.requestFullscreen) {
        this.chart.container.requestFullscreen();
      } else if (this.chart.container.webkitRequestFullscreen) {
        this.chart.container.webkitRequestFullscreen();
      } else if (this.chart.container.mozRequestFullScreen) {
        this.chart.container.mozRequestFullScreen();
      } else if (this.chart.container.msRequestFullscreen) {
        this.chart.container.msRequestFullscreen();
      }
      this.fullSizeButton.title = CHART_CONTROL_LABELS.exitFullscreen;
      this.fullSizeButton.setAttribute('aria-label', CHART_CONTROL_LABELS.exitFullscreen);
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
      } else if (document.mozCancelFullScreen) {
        document.mozCancelFullScreen();
      } else if (document.msExitFullscreen) {
        document.msExitFullscreen();
      }
      this.fullSizeButton.title = CHART_CONTROL_LABELS.enterFullscreen;
      this.fullSizeButton.setAttribute('aria-label', CHART_CONTROL_LABELS.enterFullscreen);
    }
  }

  toggleDownloadMenu(forceState) {
    const isVisible = this.downloadMenu.style.display === 'flex';
    const newState = forceState !== undefined ? forceState : !isVisible;

    this.downloadMenu.style.display = newState ? 'flex' : 'none';
    if (this.downloadButton) {
      this.downloadButton.setAttribute('aria-expanded', newState ? 'true' : 'false');
    }
    if (newState) {
      // Move focus to the first menu item so keyboard users can
      // immediately navigate with arrows (ARIA APG menu pattern).
      const firstItem = this.downloadMenu.querySelector('[role="menuitem"]');
      firstItem?.focus();
    }
  }

  /**
   * Attach hover effect to a button element
   * @param {HTMLButtonElement} button - Button element to attach hover effect
   */
  attachButtonHover(button) {
    button.addEventListener('mouseenter', () => {
      button.style.background = '#f5f5f5';
      button.style.borderColor = '#bbb';
    });
    button.addEventListener('mouseleave', () => {
      button.style.background = 'white';
      button.style.borderColor = '#ddd';
    });
  }

  /**
   * Clean up event listeners and remove DOM elements.
   */
  destroy() {
    if (this.documentClickHandler) {
      document.removeEventListener('click', this.documentClickHandler);
      this.documentClickHandler = null;
    }
    if (this.fullscreenChangeHandler) {
      document.removeEventListener('fullscreenchange', this.fullscreenChangeHandler);
      this.fullscreenChangeHandler = null;
    }
    if (this._menuKeydownHandler) {
      document.removeEventListener('keydown', this._menuKeydownHandler);
      this._menuKeydownHandler = null;
    }
    if (this.buttonContainer?.parentNode) {
      this.buttonContainer.parentNode.removeChild(this.buttonContainer);
    }
    this.buttonContainer = null;
    this.resetButton = null;
    this.fullSizeButton = null;
    this.downloadButton = null;
    this.downloadMenu = null;
    this.helpButton = null;
    this.helpPopover = null;
    this.logScaleControl = null;
    this.logScaleCheckbox = null;
  }
}
