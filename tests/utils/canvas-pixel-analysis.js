/**
 * Canvas描画結果のピクセル分析ユーティリティ
 * 色の存在確認、データポイント位置の色検証などを行う
 */

import fs from 'node:fs';
import path from 'node:path';

/**
 * 指定した座標のピクセル色を取得
 * @param {HTMLCanvasElement} canvas - 対象のcanvas要素
 * @param {number} x - X座標
 * @param {number} y - Y座標
 * @returns {Object} RGBA色情報
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
 * 色がオレンジ系統（#ff6d01）かどうかを判定
 * @param {Object} color - RGBA色情報
 * @param {number} tolerance - 許容誤差
 * @returns {boolean}
 */
export function isRedish(color, tolerance = 80) {
  // #ff6d01 (255, 109, 1) に近い色かどうか
  // より広い許容範囲で判定
  return Math.abs(color.r - 255) < tolerance && Math.abs(color.g - 109) < tolerance && Math.abs(color.b - 1) < tolerance && color.a > 0; // 透明でない色のみ
}

/**
 * 色が青系統（#1f77b4）かどうかを判定
 * @param {Object} color - RGBA色情報
 * @param {number} tolerance - 許容誤差
 * @returns {boolean}
 */
export function isBluish(color, tolerance = 80) {
  // #1f77b4 (31, 119, 180) に近い色かどうか
  return Math.abs(color.r - 31) < tolerance && Math.abs(color.g - 119) < tolerance && Math.abs(color.b - 180) < tolerance && color.a > 0; // 透明でない色のみ
}

/**
 * 色が緑系統かどうかを判定
 * @param {Object} color - RGBA色情報
 * @param {number} threshold - 閾値 (0-255)
 * @returns {boolean}
 */
export function isGreenish(color, threshold = 100) {
  return color.g > threshold && color.g > color.r + 50 && color.g > color.b + 50;
}

/**
 * 色が白系統かどうかを判定
 * @param {Object} color - RGBA色情報
 * @param {number} tolerance - 許容誤差
 * @returns {boolean}
 */
export function isWhitish(color, tolerance = 20) {
  return Math.abs(color.r - 255) < tolerance && Math.abs(color.g - 255) < tolerance && Math.abs(color.b - 255) < tolerance;
}

/**
 * 色が黒系統かどうかを判定
 * @param {Object} color - RGBA色情報
 * @param {number} threshold - 閾値 (0-255)
 * @returns {boolean}
 */
export function isBlackish(color, threshold = 50) {
  return color.r < threshold && color.g < threshold && color.b < threshold;
}

/**
 * 特定の色がCanvas内に存在するかどうかを確認
 * @param {HTMLCanvasElement} canvas - 対象のcanvas要素
 * @param {Function} colorChecker - 色判定関数
 * @returns {boolean}
 */
export function hasColorInCanvas(canvas, colorChecker) {
  const ctx = canvas.getContext('2d');
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);

  // 4つずつ（RGBA）ピクセルデータをチェック
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
 * Canvas内の色の割合を分析
 * @param {HTMLCanvasElement} canvas - 対象のcanvas要素
 * @returns {Object} 色の分析結果
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
 * 2つの色が近似しているかどうかを判定
 * @param {Object} color1 - 色1のRGBA情報
 * @param {Object} color2 - 色2のRGBA情報
 * @param {number} tolerance - 許容誤差
 * @returns {boolean}
 */
export function colorsAreSimilar(color1, color2, tolerance = 30) {
  return Math.abs(color1.r - color2.r) < tolerance && Math.abs(color1.g - color2.g) < tolerance && Math.abs(color1.b - color2.b) < tolerance;
}

/**
 * 座標からチャート上のデータポイントに変換
 * (Chartの座標系に基づく推定)
 * @param {number} step - ステップ値
 * @param {number} value - データ値
 * @param {Object} chartBounds - チャートの境界情報
 * @returns {Object} Canvas上のX,Y座標
 */
export function dataPointToCanvasCoords(step, value, chartBounds) {
  const { left, top, width, height, minStep, maxStep, minValue, maxValue } = chartBounds;

  const x = left + ((step - minStep) / (maxStep - minStep)) * width;
  const y = top + height - ((value - minValue) / (maxValue - minValue)) * height;

  return { x: Math.round(x), y: Math.round(y) };
}

/**
 * チャートの境界情報を推定
 * (Chartの典型的なマージンに基づく)
 * @param {HTMLCanvasElement} canvas - 対象のcanvas要素
 * @param {Object} data - チャートデータ
 * @returns {Object} チャートの境界情報
 */
export function estimateChartBounds(canvas, data) {
  const margin = { top: 40, right: 40, bottom: 60, left: 60 };

  let minStep = Number.POSITIVE_INFINITY;
  let maxStep = Number.NEGATIVE_INFINITY;
  let minValue = Number.POSITIVE_INFINITY;
  let maxValue = Number.NEGATIVE_INFINITY;

  // データの範囲を計算
  for (const series of data.series) {
    for (const point of series.data) {
      minStep = Math.min(minStep, point.step);
      maxStep = Math.max(maxStep, point.step);
      minValue = Math.min(minValue, point.value);
      maxValue = Math.max(maxValue, point.value);
    }
  }

  // 余裕をもたせる
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
 * CanvasをPNG画像として保存する
 * @param {HTMLCanvasElement} canvas - 保存対象のCanvas
 * @param {string} testName - テスト名（ファイル名に使用）
 * @param {string} outputDir - 出力ディレクトリ（デフォルト: logs/test-images）
 */
export function saveCanvasAsPNG(canvas, testName, outputDir = 'logs/test-images') {
  try {
    // 出力ディレクトリを作成
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    // ファイル名を生成（テスト名をサニタイズ）
    const sanitizedTestName = testName.replace(/[^a-z0-9-_]/gi, '_');
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `${sanitizedTestName}_${timestamp}.png`;
    const filepath = path.join(outputDir, filename);

    // CanvasをPNGバッファとして取得
    let buffer;
    try {
      // napi-rs/canvasの場合
      buffer = canvas.toBuffer('image/png');
    } catch (e) {
      // DOM Canvasの場合、toDataURLを使用
      const dataURL = canvas.toDataURL('image/png');
      const base64Data = dataURL.replace(/^data:image\/png;base64,/, '');
      buffer = Buffer.from(base64Data, 'base64');
    }

    // ファイルに保存
    fs.writeFileSync(filepath, buffer);

    console.log(`📸 Canvas saved as PNG: ${filepath}`);
    return filepath;
  } catch (error) {
    console.warn(`⚠️ Failed to save canvas as PNG: ${error.message}`);
    return null;
  }
}

/**
 * テスト用Canvas保存ヘルパー
 * @param {HTMLCanvasElement} canvas - 保存対象のCanvas
 * @param {string} testName - テスト名
 * @param {Object} analysis - 色分析結果（オプション）
 */
export function saveTestCanvas(canvas, testName, analysis = null) {
  const filepath = saveCanvasAsPNG(canvas, testName);

  if (analysis && filepath) {
    // 分析結果もテキストファイルとして保存
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
