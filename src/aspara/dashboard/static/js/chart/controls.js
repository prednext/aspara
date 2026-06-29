import { ICON_DOWNLOAD, ICON_FULLSCREEN, ICON_HELP, ICON_RESET_ZOOM } from '../html-utils.js';

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

    // Document click handler (stored for cleanup)
    this.documentClickHandler = null;
    // fullscreenchange handler (stored for cleanup)
    this.fullscreenChangeHandler = null;
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

    this.createResetButton();
    this.createFullSizeButton();
    this.createDownloadButton();
    this.createHelpButton();

    this.buttonContainer.appendChild(this.resetButton);
    this.buttonContainer.appendChild(this.fullSizeButton);
    this.buttonContainer.appendChild(this.downloadButton);
    this.buttonContainer.appendChild(this.helpButton);
    this.chart.container.appendChild(this.buttonContainer);
  }

  createResetButton() {
    this.resetButton = document.createElement('button');
    this.resetButton.innerHTML = ICON_RESET_ZOOM;
    this.resetButton.title = 'Reset zoom';
    this.resetButton.style.cssText = `
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

    this.attachButtonHover(this.resetButton);
    this.resetButton.addEventListener('click', () => this.chart.resetZoom());
  }

  createFullSizeButton() {
    this.fullSizeButton = document.createElement('button');
    this.fullSizeButton.innerHTML = ICON_FULLSCREEN;
    this.fullSizeButton.title = 'Enter fullscreen';
    this.fullSizeButton.style.cssText = `
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

    this.attachButtonHover(this.fullSizeButton);
    this.fullSizeButton.addEventListener('click', () => this.fitToFullSize());

    // Keep the title in sync with the actual fullscreen state so the
    // tooltip reflects what clicking the button will do (e.g. after the
    // user exits fullscreen via Esc).
    this.fullscreenChangeHandler = () => {
      if (!this.fullSizeButton) return;
      this.fullSizeButton.title = document.fullscreenElement ? 'Exit fullscreen' : 'Enter fullscreen';
    };
    document.addEventListener('fullscreenchange', this.fullscreenChangeHandler);
  }

  createDownloadButton() {
    this.downloadButton = document.createElement('button');
    this.downloadButton.innerHTML = ICON_DOWNLOAD;
    this.downloadButton.title = 'Download data';
    this.downloadButton.style.cssText = `
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
            position: relative;
        `;

    this.downloadMenu = document.createElement('div');
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

  createHelpButton() {
    this.helpButton = document.createElement('button');
    this.helpButton.innerHTML = ICON_HELP;
    this.helpButton.title = 'Chart interactions help';
    this.helpButton.style.cssText = `
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
            position: relative;
        `;

    this.helpPopover = document.createElement('div');
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
  }

  toggleHelpPopover(forceState) {
    if (!this.helpPopover) return;
    const isVisible = this.helpPopover.style.display === 'flex';
    const newState = forceState !== undefined ? forceState : !isVisible;
    this.helpPopover.style.display = newState ? 'flex' : 'none';
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
      this.fullSizeButton.title = 'Exit fullscreen';
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
      this.fullSizeButton.title = 'Enter fullscreen';
    }
  }

  toggleDownloadMenu(forceState) {
    const isVisible = this.downloadMenu.style.display === 'flex';
    const newState = forceState !== undefined ? forceState : !isVisible;

    this.downloadMenu.style.display = newState ? 'flex' : 'none';
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
  }
}
