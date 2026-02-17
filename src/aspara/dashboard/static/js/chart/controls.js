import { ICON_DOWNLOAD, ICON_FULLSCREEN, ICON_RESET_ZOOM } from '../html-utils.js';

export class ChartControls {
  constructor(chart, chartExport) {
    this.chart = chart;
    this.chartExport = chartExport;
    this.buttonContainer = null;
    this.resetButton = null;
    this.fullSizeButton = null;
    this.downloadButton = null;
    this.downloadMenu = null;

    // Document click handler (stored for cleanup)
    this.documentClickHandler = null;
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

    this.buttonContainer.appendChild(this.resetButton);
    this.buttonContainer.appendChild(this.fullSizeButton);
    this.buttonContainer.appendChild(this.downloadButton);
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
    this.fullSizeButton.title = 'Fit to full size';
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

    // Store handler for cleanup
    this.documentClickHandler = (e) => {
      if (!this.downloadButton.contains(e.target)) {
        this.toggleDownloadMenu(false);
      }
    };
    document.addEventListener('click', this.documentClickHandler);
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
    if (this.buttonContainer?.parentNode) {
      this.buttonContainer.parentNode.removeChild(this.buttonContainer);
    }
    this.buttonContainer = null;
    this.resetButton = null;
    this.fullSizeButton = null;
    this.downloadButton = null;
    this.downloadMenu = null;
  }
}
