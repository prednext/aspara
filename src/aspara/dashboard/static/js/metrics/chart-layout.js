/**
 * Shared chart layout utilities.
 * Provides common layout calculation and grid management for chart pages.
 */

/** Chart base width map for S/M/L sizes */
export const CHART_BASE_WIDTH_MAP = {
  S: 300,
  M: 400,
  L: 600,
};

/** Chart container padding map for S/M/L sizes (corresponds to Tailwind p-3/p-6) */
export const CHART_PADDING_MAP = {
  S: 12, // p-3 = 12px
  M: 24, // p-6 = 24px
  L: 24, // p-6 = 24px
};

/** LocalStorage key for chart size preference */
export const CHART_SIZE_KEY = 'chart_size';

/**
 * Calculate chart dimensions based on container width and chart size.
 *
 * @param {number} containerWidth - Width of the container in pixels
 * @param {string} chartSize - Chart size ('S', 'M', or 'L')
 * @param {number} [gap=32] - Gap between charts in pixels
 * @returns {{ columns: number, chartWidth: number, chartHeight: number, gap: number, padding: number }}
 */
export function calculateChartDimensions(containerWidth, chartSize, gap = 32) {
  const baseWidth = CHART_BASE_WIDTH_MAP[chartSize] || CHART_BASE_WIDTH_MAP.M;
  const padding = CHART_PADDING_MAP[chartSize] || CHART_PADDING_MAP.M;
  const aspectRatio = 16 / 9;

  const columns = Math.max(1, Math.floor(containerWidth / baseWidth));
  const totalGap = gap * (columns - 1);
  const chartWidth = (containerWidth - totalGap) / columns;

  // Calculate height based on content width after padding
  const contentWidth = chartWidth - padding * 2;
  const chartHeight = contentWidth / aspectRatio;

  return { columns, chartWidth, chartHeight, gap, padding };
}

/**
 * Apply grid layout to a container element.
 *
 * @param {HTMLElement} container - Container element to apply grid to
 * @param {number} columns - Number of grid columns
 * @param {number} gap - Gap between items in pixels
 */
export function applyGridLayout(container, columns, gap) {
  container.style.display = 'grid';
  container.style.gridTemplateColumns = `repeat(${columns}, 1fr)`;
  container.style.gap = `${gap}px`;
  container.classList.remove('space-y-8');
}

/**
 * Update heights of chart elements in a container.
 *
 * @param {HTMLElement} container - Container element with chart divs
 * @param {number} chartHeight - Height to apply in pixels
 * @param {string} [selector='[id^="chart-"]'] - CSS selector for chart elements
 */
export function updateChartHeights(container, chartHeight, selector = '[id^="chart-"]') {
  const chartDivs = container.querySelectorAll(selector);
  for (const chartDiv of chartDivs) {
    chartDiv.style.height = `${chartHeight}px`;
  }
}

/**
 * Update padding of chart containers based on chart size.
 *
 * @param {HTMLElement} container - Container element with chart containers
 * @param {string} chartSize - Chart size ('S', 'M', or 'L')
 */
export function updateContainerPadding(container, chartSize) {
  const chartContainers = container.querySelectorAll(':scope > div');
  const paddingClass = chartSize === 'S' ? 'p-3' : 'p-6';
  const removePaddingClass = chartSize === 'S' ? 'p-6' : 'p-3';

  for (const chartContainer of chartContainers) {
    chartContainer.classList.remove(removePaddingClass);
    chartContainer.classList.add(paddingClass);
  }
}

/**
 * Update size toggle button styles.
 *
 * @param {Object} buttons - Object with size keys (S, M, L) and button elements as values
 * @param {string} activeSize - Currently active size
 */
export function updateSizeButtonStyles(buttons, activeSize) {
  for (const [size, button] of Object.entries(buttons)) {
    if (!button) continue;

    if (size === activeSize) {
      button.classList.add('bg-action', 'text-white');
      button.classList.remove('bg-base-surface', 'text-text-primary', 'hover:bg-base-bg');
    } else {
      button.classList.add('bg-base-surface', 'text-text-primary', 'hover:bg-base-bg');
      button.classList.remove('bg-action', 'text-white', 'hover:bg-action-hover');
    }
  }
}
