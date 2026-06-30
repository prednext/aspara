/**
 * Pixel analysis utilities for Canvas rendering results
 * Performs color presence checks, color verification at data point positions, etc.
 */

import fs from 'node:fs';
import path from 'node:path';

/**
 * Get the pixel color at the given coordinates
 * @param {HTMLCanvasElement} canvas - target canvas element
 * @param {number} x - X coordinate
 * @param {number} y - Y coordinate
 * @returns {Object} RGBA color info
 */
export function getPixelColor(canvas, x, y) {
  const ctx = canvas.getContext('2d');
  const imageData = ctx.getImageData(x, y, 1, 1);
  const data = imageData.data;

  return {
    r: data[0],
    g: data[1],
    b: data[2],
    a: data[3],
  };
}

/**
 * Determine whether the color is in the orange family (#ff6d01)
 * @param {Object} color - RGBA color info
 * @param {number} tolerance - tolerance
 * @returns {boolean}
 */
export function isRedish(color, tolerance = 80) {
  // Whether the color is close to #ff6d01 (255, 109, 1)
  // Use a wider tolerance for the check
  return Math.abs(color.r - 255) < tolerance && Math.abs(color.g - 109) < tolerance && Math.abs(color.b - 1) < tolerance && color.a > 0; // only non-transparent colors
}

/**
 * Determine whether the color is in the blue family (#1f77b4)
 * @param {Object} color - RGBA color info
 * @param {number} tolerance - tolerance
 * @returns {boolean}
 */
export function isBluish(color, tolerance = 80) {
  // Whether the color is close to #1f77b4 (31, 119, 180)
  return Math.abs(color.r - 31) < tolerance && Math.abs(color.g - 119) < tolerance && Math.abs(color.b - 180) < tolerance && color.a > 0; // only non-transparent colors
}

/**
 * Determine whether the color is in the green family
 * @param {Object} color - RGBA color info
 * @param {number} threshold - threshold (0-255)
 * @returns {boolean}
 */
export function isGreenish(color, threshold = 100) {
  return color.g > threshold && color.g > color.r + 50 && color.g > color.b + 50;
}

/**
 * Determine whether the color is in the white family
 * @param {Object} color - RGBA color info
 * @param {number} tolerance - tolerance
 * @returns {boolean}
 */
export function isWhitish(color, tolerance = 20) {
  return Math.abs(color.r - 255) < tolerance && Math.abs(color.g - 255) < tolerance && Math.abs(color.b - 255) < tolerance;
}

/**
 * Determine whether the color is in the black family
 * @param {Object} color - RGBA color info
 * @param {number} threshold - threshold (0-255)
 * @returns {boolean}
 */
export function isBlackish(color, threshold = 50) {
  return color.r < threshold && color.g < threshold && color.b < threshold;
}

/**
 * Check whether a specific color exists within the canvas
 * @param {HTMLCanvasElement} canvas - target canvas element
 * @param {Function} colorChecker - color check function
 * @returns {boolean}
 */
export function hasColorInCanvas(canvas, colorChecker) {
  const ctx = canvas.getContext('2d');
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);

  // Check pixel data in steps of 4 (RGBA)
  for (let i = 0; i < imageData.data.length; i += 4) {
    const color = {
      r: imageData.data[i],
      g: imageData.data[i + 1],
      b: imageData.data[i + 2],
      a: imageData.data[i + 3],
    };

    if (colorChecker(color)) {
      return true;
    }
  }

  return false;
}

/**
 * Analyze the ratio of colors within the canvas
 * @param {HTMLCanvasElement} canvas - target canvas element
 * @returns {Object} color analysis result
 */
export function analyzeCanvasColors(canvas) {
  const ctx = canvas.getContext('2d');
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const totalPixels = imageData.data.length / 4;

  let whitePixels = 0;
  let redPixels = 0;
  let bluePixels = 0;
  let greenPixels = 0;
  let blackPixels = 0;
  let otherPixels = 0;

  for (let i = 0; i < imageData.data.length; i += 4) {
    const color = {
      r: imageData.data[i],
      g: imageData.data[i + 1],
      b: imageData.data[i + 2],
      a: imageData.data[i + 3],
    };

    if (isWhitish(color)) {
      whitePixels++;
    } else if (isRedish(color)) {
      redPixels++;
    } else if (isBluish(color)) {
      bluePixels++;
    } else if (isGreenish(color)) {
      greenPixels++;
    } else if (isBlackish(color)) {
      blackPixels++;
    } else {
      otherPixels++;
    }
  }

  return {
    totalPixels,
    white: whitePixels / totalPixels,
    red: redPixels / totalPixels,
    blue: bluePixels / totalPixels,
    green: greenPixels / totalPixels,
    black: blackPixels / totalPixels,
    other: otherPixels / totalPixels,
    hasDataColors: redPixels + bluePixels + greenPixels + otherPixels + blackPixels > 0,
    backgroundRatio: whitePixels / totalPixels,
  };
}

/**
 * Determine whether two colors are similar
 * @param {Object} color1 - RGBA info of color 1
 * @param {Object} color2 - RGBA info of color 2
 * @param {number} tolerance - tolerance
 * @returns {boolean}
 */
export function colorsAreSimilar(color1, color2, tolerance = 30) {
  return Math.abs(color1.r - color2.r) < tolerance && Math.abs(color1.g - color2.g) < tolerance && Math.abs(color1.b - color2.b) < tolerance;
}

/**
 * Convert coordinates to a data point on the chart
 * (Estimation based on the Chart coordinate system)
 * @param {number} step - step value
 * @param {number} value - data value
 * @param {Object} chartBounds - chart bounds info
 * @returns {Object} X, Y coordinates on the canvas
 */
export function dataPointToCanvasCoords(step, value, chartBounds) {
  const { left, top, width, height, minStep, maxStep, minValue, maxValue } = chartBounds;

  const x = left + ((step - minStep) / (maxStep - minStep)) * width;
  const y = top + height - ((value - minValue) / (maxValue - minValue)) * height;

  return { x: Math.round(x), y: Math.round(y) };
}

/**
 * Estimate the chart bounds
 * (Based on typical Chart margins)
 * @param {HTMLCanvasElement} canvas - target canvas element
 * @param {Object} data - chart data
 * @returns {Object} chart bounds info
 */
export function estimateChartBounds(canvas, data) {
  const margin = { top: 40, right: 40, bottom: 60, left: 60 };

  let minStep = Number.POSITIVE_INFINITY;
  let maxStep = Number.NEGATIVE_INFINITY;
  let minValue = Number.POSITIVE_INFINITY;
  let maxValue = Number.NEGATIVE_INFINITY;

  // Compute the data range
  for (const series of data.series) {
    for (const point of series.data) {
      minStep = Math.min(minStep, point.step);
      maxStep = Math.max(maxStep, point.step);
      minValue = Math.min(minValue, point.value);
      maxValue = Math.max(maxValue, point.value);
    }
  }

  // Add some padding
  const stepPadding = (maxStep - minStep) * 0.05;
  const valuePadding = (maxValue - minValue) * 0.05;

  return {
    left: margin.left,
    top: margin.top,
    width: canvas.width - margin.left - margin.right,
    height: canvas.height - margin.top - margin.bottom,
    minStep: minStep - stepPadding,
    maxStep: maxStep + stepPadding,
    minValue: minValue - valuePadding,
    maxValue: maxValue + valuePadding,
  };
}

/**
 * Save the canvas as a PNG image
 * @param {HTMLCanvasElement} canvas - canvas to save
 * @param {string} testName - test name (used as the file name)
 * @param {string} outputDir - output directory (default: logs/test-images)
 */
export function saveCanvasAsPNG(canvas, testName, outputDir = 'logs/test-images') {
  try {
    // Create the output directory
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    // Generate the file name (sanitize the test name)
    const sanitizedTestName = testName.replace(/[^a-z0-9-_]/gi, '_');
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `${sanitizedTestName}_${timestamp}.png`;
    const filepath = path.join(outputDir, filename);

    // Get the canvas as a PNG buffer
    let buffer;
    try {
      // For napi-rs/canvas
      buffer = canvas.toBuffer('image/png');
    } catch (e) {
      // For DOM Canvas, use toDataURL
      const dataURL = canvas.toDataURL('image/png');
      const base64Data = dataURL.replace(/^data:image\/png;base64,/, '');
      buffer = Buffer.from(base64Data, 'base64');
    }

    // Save to file
    fs.writeFileSync(filepath, buffer);

    console.log(`📸 Canvas saved as PNG: ${filepath}`);
    return filepath;
  } catch (error) {
    console.warn(`⚠️ Failed to save canvas as PNG: ${error.message}`);
    return null;
  }
}

/**
 * Helper to save a canvas for testing
 * @param {HTMLCanvasElement} canvas - canvas to save
 * @param {string} testName - test name
 * @param {Object} analysis - color analysis result (optional)
 */
export function saveTestCanvas(canvas, testName, analysis = null) {
  const filepath = saveCanvasAsPNG(canvas, testName);

  if (analysis && filepath) {
    // Also save the analysis result as a text file
    const analysisFile = filepath.replace('.png', '_analysis.json');
    const analysisData = {
      testName,
      timestamp: new Date().toISOString(),
      canvasSize: {
        width: canvas.width,
        height: canvas.height,
      },
      colorAnalysis: analysis,
    };

    try {
      fs.writeFileSync(analysisFile, JSON.stringify(analysisData, null, 2));
      console.log(`📊 Analysis saved: ${analysisFile}`);
    } catch (error) {
      console.warn(`⚠️ Failed to save analysis: ${error.message}`);
    }
  }

  return filepath;
}
