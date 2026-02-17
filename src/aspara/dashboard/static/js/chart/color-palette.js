/**
 * ChartColorPalette - Color management for chart series
 * Handles color generation, style assignment, and run-to-style mapping
 */
export class ChartColorPalette {
  constructor() {
    // Modern 16-color base palette with well-distributed hues for easy differentiation
    // Colors are arranged by hue (0-360°) with ~22.5° spacing for maximum visual distinction
    // Red-family colors and dark blues have varied saturation for better distinction
    this.baseColors = [
      '#FF3B47', // red (0°) - high saturation
      '#F77F00', // orange (30°)
      '#FCBF49', // yellow (45°)
      '#06D6A0', // mint/turquoise (165°)
      '#118AB2', // blue (195°)
      '#69808b', // dark blue (200°) - higher saturation, more vivid
      '#4361EE', // bright blue (225°)
      '#7209B7', // purple (270°)
      '#E85D9A', // magenta (330°) - medium saturation, lighter
      '#B8252D', // crimson (355°) - lower saturation, darker
      '#F4A261', // peach (35°)
      '#2A9D8F', // teal (170°)
      '#408828', // dark teal (190°) - lower saturation, more muted
      '#3A86FF', // sky blue (215°)
      '#8338EC', // violet (265°)
      '#FF1F7D', // hot pink (340°) - very high saturation
    ];

    // Border dash patterns for additional differentiation
    this.borderDashPatterns = [
      [], // solid
      [6, 4], // dashed
      [2, 3], // dotted
      [10, 3, 2, 3], // dash-dot
    ];

    // Registry to maintain stable run->style mapping
    this.runStyleRegistry = new Map();
    this.nextStyleIndex = 0;
  }

  /**
   * Convert hex color to RGB
   * @param {string} hex - Hex color string
   * @returns {Object|null} RGB object or null if invalid
   */
  hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result
      ? {
          r: Number.parseInt(result[1], 16),
          g: Number.parseInt(result[2], 16),
          b: Number.parseInt(result[3], 16),
        }
      : null;
  }

  /**
   * Convert RGB to HSL
   * @param {number} r - Red (0-255)
   * @param {number} g - Green (0-255)
   * @param {number} b - Blue (0-255)
   * @returns {Object} HSL object
   */
  rgbToHsl(r, g, b) {
    const rNorm = r / 255;
    const gNorm = g / 255;
    const bNorm = b / 255;

    const max = Math.max(rNorm, gNorm, bNorm);
    const min = Math.min(rNorm, gNorm, bNorm);
    let h;
    let s;
    const l = (max + min) / 2;

    if (max === min) {
      h = 0;
      s = 0;
    } else {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);

      switch (max) {
        case rNorm:
          h = ((gNorm - bNorm) / d + (gNorm < bNorm ? 6 : 0)) / 6;
          break;
        case gNorm:
          h = ((bNorm - rNorm) / d + 2) / 6;
          break;
        case bNorm:
          h = ((rNorm - gNorm) / d + 4) / 6;
          break;
      }
    }

    return { h: h * 360, s: s * 100, l: l * 100 };
  }

  /**
   * Apply variant transformation to HSL color
   * @param {Object} hsl - HSL color object
   * @param {number} variantIndex - Variant index (0-2)
   * @returns {Object} Modified HSL object
   */
  applyVariant(hsl, variantIndex) {
    const variants = [
      { sDelta: 0, lDelta: 0 }, // normal
      { sDelta: -15, lDelta: -6 }, // muted
      { sDelta: 8, lDelta: 6 }, // bright
    ];

    const variant = variants[variantIndex];
    let s = hsl.s + variant.sDelta;
    let l = hsl.l + variant.lDelta;

    // Clamp to safe ranges
    s = Math.max(35, Math.min(95, s));
    l = Math.max(30, Math.min(70, l));

    return { h: hsl.h, s, l };
  }

  /**
   * Convert HSL to CSS string
   * @param {Object} hsl - HSL color object
   * @returns {string} CSS HSL string
   */
  hslToString(hsl) {
    return `hsl(${Math.round(hsl.h)}, ${Math.round(hsl.s)}%, ${Math.round(hsl.l)}%)`;
  }

  /**
   * Generate style for a given style index
   * @param {number} styleIndex - Style index
   * @returns {Object} Style object with borderColor, backgroundColor, borderDash
   */
  generateStyle(styleIndex) {
    const M = this.baseColors.length; // 16
    const V = 3; // variants
    const D = this.borderDashPatterns.length; // 4

    const baseIndex = styleIndex % M;
    const variantIndex = Math.floor(styleIndex / M) % V;
    const dashIndex = Math.floor(styleIndex / (M * V)) % D;

    // Get base color and convert to HSL
    const hex = this.baseColors[baseIndex];
    const rgb = this.hexToRgb(hex);
    const hsl = this.rgbToHsl(rgb.r, rgb.g, rgb.b);

    // Apply variant
    const variantHsl = this.applyVariant(hsl, variantIndex);
    const borderColor = this.hslToString(variantHsl);

    // Get border dash pattern
    const borderDash = this.borderDashPatterns[dashIndex];

    return {
      borderColor,
      backgroundColor: borderColor,
      borderDash,
    };
  }

  /**
   * Ensure all runs have stable styles assigned
   * @param {Array<string>} runIds - Array of run IDs
   */
  ensureRunStyles(runIds) {
    // Sort run IDs for stable ordering
    const sortedRunIds = [...new Set(runIds)].sort();

    for (const runId of sortedRunIds) {
      if (!this.runStyleRegistry.has(runId)) {
        const style = this.generateStyle(this.nextStyleIndex);
        this.runStyleRegistry.set(runId, style);
        this.nextStyleIndex++;
      }
    }
  }

  /**
   * Get style for a specific run
   * @param {string} runId - Run ID
   * @returns {Object} Style object
   */
  getRunStyle(runId) {
    return this.runStyleRegistry.get(runId) || this.generateStyle(0);
  }

  /**
   * Reset the style registry
   */
  reset() {
    this.runStyleRegistry.clear();
    this.nextStyleIndex = 0;
  }
}
