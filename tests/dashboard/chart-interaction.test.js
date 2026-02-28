/**
 * Unit tests for ChartInteraction
 */

import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { ChartInteraction } from '../../src/aspara/dashboard/static/js/chart/interaction.js';

// Mock interaction-utils
vi.mock('../../src/aspara/dashboard/static/js/chart/interaction-utils.js', () => ({
  binarySearchByStep: vi.fn(),
  calculateDataRanges: vi.fn(),
  findNearestStepBinary: vi.fn(),
}));

import { binarySearchByStep, calculateDataRanges, findNearestStepBinary } from '../../src/aspara/dashboard/static/js/chart/interaction-utils.js';

function createMockChart() {
  const canvas = document.createElement('canvas');
  canvas.width = 800;
  canvas.height = 600;
  // Mock getBoundingClientRect
  canvas.getBoundingClientRect = () => ({ left: 0, top: 0, width: 800, height: 600 });

  return {
    canvas,
    ctx: {
      fillStyle: '',
      strokeStyle: '',
      lineWidth: 1,
      font: '',
      textAlign: '',
      textBaseline: '',
      beginPath: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      stroke: vi.fn(),
      fillRect: vi.fn(),
      strokeRect: vi.fn(),
      fillText: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      setLineDash: vi.fn(),
      measureText: vi.fn(() => ({ width: 50 })),
    },
    data: null,
    width: 800,
    height: 600,
    zoomState: { active: false, startX: 0, startY: 0, currentX: 0, currentY: 0 },
    zoom: {},
    hoverPoint: null,
    draw: vi.fn(),
    resetZoom: vi.fn(),
    onZoomChange: null,
    constructor: { MARGIN: 60, MIN_DRAG_DISTANCE: 5, Y_PADDING_RATIO: 0.1 },
    colorPalette: {
      getRunStyle: vi.fn(() => ({ borderColor: '#ff0000', borderDash: [] })),
    },
  };
}

describe('ChartInteraction', () => {
  let chart;
  let renderer;
  let interaction;

  beforeEach(() => {
    chart = createMockChart();
    renderer = { drawRoundedRect: vi.fn() };
    interaction = new ChartInteraction(chart, renderer);
    vi.clearAllMocks();
  });

  afterEach(() => {
    interaction.removeEventListeners();
  });

  describe('constructor', () => {
    test('should initialize with default state', () => {
      expect(interaction.chart).toBe(chart);
      expect(interaction.renderer).toBe(renderer);
      expect(interaction._cachedRanges).toBeNull();
      expect(interaction._lastDataRef).toBeNull();
      expect(interaction._pendingMouseMoveDraw).toBe(false);
    });
  });

  describe('invalidateRangesCache', () => {
    test('should clear cached ranges', () => {
      interaction._cachedRanges = { xMin: 0 };
      interaction._lastDataRef = [];
      interaction.invalidateRangesCache();
      expect(interaction._cachedRanges).toBeNull();
      expect(interaction._lastDataRef).toBeNull();
    });
  });

  describe('_getDataRanges', () => {
    test('should calculate and cache ranges on first call', () => {
      const series = [{ data: { steps: [0, 1], values: [10, 20] } }];
      chart.data = { series };
      const ranges = { xMin: 0, xMax: 1, yMin: 10, yMax: 20 };
      calculateDataRanges.mockReturnValue(ranges);

      const result = interaction._getDataRanges();

      expect(calculateDataRanges).toHaveBeenCalledWith(series);
      expect(result).toBe(ranges);
    });

    test('should return cached ranges when data reference unchanged', () => {
      const series = [{ data: { steps: [0, 1], values: [10, 20] } }];
      chart.data = { series };
      const ranges = { xMin: 0, xMax: 1, yMin: 10, yMax: 20 };
      calculateDataRanges.mockReturnValue(ranges);

      interaction._getDataRanges();
      calculateDataRanges.mockClear();
      const result = interaction._getDataRanges();

      expect(calculateDataRanges).not.toHaveBeenCalled();
      expect(result).toBe(ranges);
    });

    test('should recalculate when data reference changes', () => {
      chart.data = { series: [{ data: { steps: [0], values: [1] } }] };
      calculateDataRanges.mockReturnValue({ xMin: 0, xMax: 0, yMin: 1, yMax: 1 });
      interaction._getDataRanges();

      const newSeries = [{ data: { steps: [0, 1], values: [1, 2] } }];
      chart.data = { series: newSeries };
      const newRanges = { xMin: 0, xMax: 1, yMin: 1, yMax: 2 };
      calculateDataRanges.mockReturnValue(newRanges);

      const result = interaction._getDataRanges();
      expect(calculateDataRanges).toHaveBeenCalledWith(newSeries);
      expect(result).toBe(newRanges);
    });

    test('should handle null data', () => {
      chart.data = null;
      calculateDataRanges.mockReturnValue(null);
      const result = interaction._getDataRanges();
      expect(calculateDataRanges).toHaveBeenCalledWith([]);
      expect(result).toBeNull();
    });
  });

  describe('setupEventListeners / removeEventListeners', () => {
    test('should set up all event handlers', () => {
      interaction.setupEventListeners();

      expect(interaction.mousemoveHandler).not.toBeNull();
      expect(interaction.mouseleaveHandler).not.toBeNull();
      expect(interaction.mousedownHandler).not.toBeNull();
      expect(interaction.mouseupHandler).not.toBeNull();
      expect(interaction.dblclickHandler).not.toBeNull();
      expect(interaction.contextmenuHandler).not.toBeNull();
    });

    test('should clear all handlers on remove', () => {
      interaction.setupEventListeners();
      interaction.removeEventListeners();

      expect(interaction.mousemoveHandler).toBeNull();
      expect(interaction.mouseleaveHandler).toBeNull();
      expect(interaction.mousedownHandler).toBeNull();
      expect(interaction.mouseupHandler).toBeNull();
      expect(interaction.dblclickHandler).toBeNull();
      expect(interaction.contextmenuHandler).toBeNull();
    });

    test('should handle removeEventListeners when no canvas', () => {
      chart.canvas = null;
      expect(() => interaction.removeEventListeners()).not.toThrow();
    });

    test('should handle removeEventListeners when handlers are null', () => {
      expect(() => interaction.removeEventListeners()).not.toThrow();
    });
  });

  describe('handleMouseMove', () => {
    test('should update zoom state when zoom is active', () => {
      chart.zoomState.active = true;
      interaction.setupEventListeners();

      interaction.handleMouseMove({ clientX: 100, clientY: 200 });

      expect(chart.zoomState.currentX).toBe(100);
      expect(chart.zoomState.currentY).toBe(200);
    });

    test('should return early when no data', () => {
      chart.data = null;
      interaction.setupEventListeners();

      interaction.handleMouseMove({ clientX: 100, clientY: 100 });
      expect(chart.hoverPoint).toBeNull();
    });

    test('should return early when series is empty', () => {
      chart.data = { series: [] };
      interaction.setupEventListeners();

      interaction.handleMouseMove({ clientX: 100, clientY: 100 });
      expect(chart.hoverPoint).toBeNull();
    });

    test('should set hoverPoint when nearest point found', () => {
      chart.data = { series: [{ name: 'loss', data: { steps: [0, 1], values: [1, 2] } }] };
      calculateDataRanges.mockReturnValue({ xMin: 0, xMax: 1, yMin: 1, yMax: 2 });
      findNearestStepBinary.mockReturnValue(0);
      binarySearchByStep.mockReturnValue({ step: 0, value: 1 });
      interaction.setupEventListeners();

      interaction.handleMouseMove({ clientX: 400, clientY: 300 });

      expect(chart.hoverPoint).not.toBeNull();
      expect(chart.hoverPoint.step).toBe(0);
    });

    test('should clear hoverPoint when no nearest point and had previous hover', () => {
      chart.data = { series: [{ name: 'loss', data: { steps: [0], values: [1] } }] };
      chart.hoverPoint = { points: [], step: 0 };
      calculateDataRanges.mockReturnValue({ xMin: 0, xMax: 1, yMin: 1, yMax: 2 });
      findNearestStepBinary.mockReturnValue(null);
      interaction.setupEventListeners();

      interaction.handleMouseMove({ clientX: 400, clientY: 300 });

      expect(chart.hoverPoint).toBeNull();
    });
  });

  describe('handleMouseLeave', () => {
    test('should clear hover point and redraw', () => {
      chart.hoverPoint = { points: [], step: 0 };
      interaction.handleMouseLeave();

      expect(chart.hoverPoint).toBeNull();
      expect(chart.draw).toHaveBeenCalled();
    });

    test('should not draw when no hover point', () => {
      chart.hoverPoint = null;
      interaction.handleMouseLeave();

      expect(chart.draw).not.toHaveBeenCalled();
    });
  });

  describe('handleMouseDown', () => {
    test('should start zoom on left click inside plot area', () => {
      // MARGIN = 60, width = 800, so plotWidth = 680
      // Inside plot area: x=100 (>60), y=100 (>60)
      interaction.handleMouseDown({ button: 0, clientX: 100, clientY: 100 });

      expect(chart.zoomState.active).toBe(true);
      expect(chart.zoomState.startX).toBe(100);
      expect(chart.zoomState.startY).toBe(100);
    });

    test('should ignore non-left clicks', () => {
      interaction.handleMouseDown({ button: 2, clientX: 100, clientY: 100 });
      expect(chart.zoomState.active).toBe(false);
    });

    test('should ignore clicks outside plot area', () => {
      // x=10 is less than MARGIN (60)
      interaction.handleMouseDown({ button: 0, clientX: 10, clientY: 10 });
      expect(chart.zoomState.active).toBe(false);
    });
  });

  describe('handleMouseUp', () => {
    test('should do nothing when zoom not active', () => {
      chart.zoomState.active = false;
      interaction.handleMouseUp({ button: 0 });
      expect(chart.draw).not.toHaveBeenCalled();
    });

    test('should cancel zoom on small drag', () => {
      chart.zoomState.active = true;
      chart.zoomState.startX = 100;
      chart.zoomState.startY = 100;
      chart.zoomState.currentX = 102;
      chart.zoomState.currentY = 101;

      interaction.handleMouseUp({ button: 0 });

      expect(chart.zoomState.active).toBe(false);
      expect(chart.draw).toHaveBeenCalled();
    });

    test('should apply zoom on sufficient drag', () => {
      chart.data = { series: [{ data: { steps: [0, 10], values: [0, 100] } }] };
      calculateDataRanges.mockReturnValue({ xMin: 0, xMax: 10, yMin: 0, yMax: 100 });

      chart.zoomState.active = true;
      chart.zoomState.startX = 100;
      chart.zoomState.startY = 100;
      chart.zoomState.currentX = 200;
      chart.zoomState.currentY = 200;

      interaction.handleMouseUp({ button: 0 });

      expect(chart.zoomState.active).toBe(false);
      expect(chart.zoom.x).toBeDefined();
      expect(chart.zoom.y).toBeDefined();
    });
  });

  describe('findNearestPoint', () => {
    test('should return null when no data', () => {
      chart.data = null;
      expect(interaction.findNearestPoint(400, 300)).toBeNull();
    });

    test('should return null when mouse outside plot area', () => {
      chart.data = { series: [{ data: { steps: [0], values: [1] } }] };
      // x=10 is outside margin
      expect(interaction.findNearestPoint(10, 300)).toBeNull();
    });

    test('should return null when no ranges', () => {
      chart.data = { series: [{ data: { steps: [0], values: [1] } }] };
      calculateDataRanges.mockReturnValue(null);
      expect(interaction.findNearestPoint(400, 300)).toBeNull();
    });

    test('should use zoom ranges when zoomed', () => {
      chart.data = { series: [{ name: 's1', data: { steps: [0, 5, 10], values: [1, 2, 3] } }] };
      chart.zoom.x = { min: 2, max: 8 };
      chart.zoom.y = { min: 1.5, max: 2.5 };
      calculateDataRanges.mockReturnValue({ xMin: 0, xMax: 10, yMin: 1, yMax: 3 });
      findNearestStepBinary.mockReturnValue(5);
      binarySearchByStep.mockReturnValue({ step: 5, value: 2 });

      const result = interaction.findNearestPoint(400, 300);
      expect(result).not.toBeNull();
      expect(result.step).toBe(5);
    });

    test('should return null when no points match', () => {
      chart.data = { series: [{ name: 's1', data: { steps: [0], values: [1] } }] };
      calculateDataRanges.mockReturnValue({ xMin: 0, xMax: 1, yMin: 1, yMax: 2 });
      findNearestStepBinary.mockReturnValue(0);
      binarySearchByStep.mockReturnValue(null);

      expect(interaction.findNearestPoint(400, 300)).toBeNull();
    });

    test('should skip series with no data', () => {
      chart.data = {
        series: [
          { name: 's1', data: null },
          { name: 's2', data: { steps: [0], values: [1] } },
        ],
      };
      calculateDataRanges.mockReturnValue({ xMin: 0, xMax: 1, yMin: 1, yMax: 2 });
      findNearestStepBinary.mockReturnValue(0);
      binarySearchByStep.mockReturnValue({ step: 0, value: 1 });

      const result = interaction.findNearestPoint(400, 300);
      expect(result).not.toBeNull();
      // binarySearchByStep should only be called once (for s2)
      expect(binarySearchByStep).toHaveBeenCalledTimes(1);
    });
  });

  describe('applyZoom', () => {
    test('should do nothing when no data', () => {
      chart.data = null;
      interaction.applyZoom();
      expect(chart.draw).not.toHaveBeenCalled();
    });

    test('should do nothing when no ranges', () => {
      chart.data = { series: [{ data: { steps: [0], values: [1] } }] };
      calculateDataRanges.mockReturnValue(null);
      interaction.applyZoom();
      expect(chart.draw).not.toHaveBeenCalled();
    });

    test('should call onZoomChange callback if set', () => {
      chart.data = { series: [{ data: { steps: [0, 10], values: [0, 100] } }] };
      calculateDataRanges.mockReturnValue({ xMin: 0, xMax: 10, yMin: 0, yMax: 100 });
      chart.zoomState = { startX: 100, startY: 100, currentX: 300, currentY: 300 };
      chart.onZoomChange = vi.fn();

      interaction.applyZoom();

      expect(chart.onZoomChange).toHaveBeenCalledWith({ x: chart.zoom.x, y: chart.zoom.y });
      expect(chart.draw).toHaveBeenCalled();
    });

    test('should use existing zoom ranges when already zoomed', () => {
      chart.data = { series: [{ data: { steps: [0, 10], values: [0, 100] } }] };
      calculateDataRanges.mockReturnValue({ xMin: 0, xMax: 10, yMin: 0, yMax: 100 });
      chart.zoom.x = { min: 2, max: 8 };
      chart.zoom.y = { min: 20, max: 80 };
      chart.zoomState = { startX: 100, startY: 100, currentX: 300, currentY: 300 };

      interaction.applyZoom();

      expect(chart.zoom.x).toBeDefined();
      expect(chart.draw).toHaveBeenCalled();
    });
  });

  describe('drawHoverEffects', () => {
    test('should return early when no hover point', () => {
      chart.hoverPoint = null;
      interaction.drawHoverEffects();
      expect(chart.ctx.beginPath).not.toHaveBeenCalled();
    });

    test('should draw points and call drawTooltip', () => {
      chart.hoverPoint = {
        step: 0,
        points: [{ x: 100, y: 200, color: '#ff0000', data: { step: 0, value: 1 }, series: 'loss' }],
      };

      interaction.drawHoverEffects();

      expect(chart.ctx.beginPath).toHaveBeenCalled();
      expect(chart.ctx.arc).toHaveBeenCalled();
      expect(chart.ctx.fill).toHaveBeenCalled();
    });
  });

  describe('drawZoomSelection', () => {
    test('should return early when zoom not active', () => {
      chart.zoomState.active = false;
      interaction.drawZoomSelection();
      expect(chart.ctx.fillRect).not.toHaveBeenCalled();
    });

    test('should draw zoom rectangle when active', () => {
      chart.zoomState.active = true;
      chart.zoomState.startX = 100;
      chart.zoomState.startY = 100;
      chart.zoomState.currentX = 300;
      chart.zoomState.currentY = 300;

      interaction.drawZoomSelection();

      expect(chart.ctx.fillRect).toHaveBeenCalled();
      expect(chart.ctx.strokeRect).toHaveBeenCalled();
    });
  });

  describe('drawTooltip', () => {
    test('should return early when no hover point', () => {
      chart.hoverPoint = null;
      interaction.drawTooltip();
      expect(chart.ctx.fillText).not.toHaveBeenCalled();
    });

    test('should reposition tooltip when it exceeds canvas width', () => {
      chart.hoverPoint = {
        step: 10,
        points: [{ x: 780, y: 200, color: '#ff0000', data: { step: 10, value: 1.5 }, series: 'loss' }],
      };
      // measureText returns width=50, so tooltip will be wide enough to overflow
      chart.ctx.measureText = vi.fn(() => ({ width: 200 }));

      interaction.drawTooltip();

      expect(chart.ctx.fillText).toHaveBeenCalled();
    });

    test('should reposition tooltip when it goes above canvas', () => {
      chart.hoverPoint = {
        step: 5,
        points: [{ x: 100, y: 5, color: '#ff0000', data: { step: 5, value: 2.0 }, series: 'loss' }],
      };

      interaction.drawTooltip();

      expect(chart.ctx.fillText).toHaveBeenCalled();
    });

    test('should handle series with borderDash', () => {
      chart.hoverPoint = {
        step: 0,
        points: [{ x: 100, y: 200, color: '#ff0000', data: { step: 0, value: 1 }, series: 'train-loss' }],
      };
      chart.colorPalette.getRunStyle.mockReturnValue({ borderColor: '#ff0000', borderDash: [4, 4] });

      interaction.drawTooltip();

      expect(chart.ctx.setLineDash).toHaveBeenCalledWith([4, 4]);
    });
  });

  describe('_scheduleMouseMoveDraw', () => {
    test('should not schedule when already pending', () => {
      interaction._pendingMouseMoveDraw = true;
      const spy = vi.spyOn(globalThis, 'requestAnimationFrame');

      interaction._scheduleMouseMoveDraw();

      expect(spy).not.toHaveBeenCalled();
      spy.mockRestore();
    });
  });
});
