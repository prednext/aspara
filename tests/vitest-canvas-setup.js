/**
 * Vitest用のCanvas設定
 * @napi-rs/canvasを使ってテスト環境でCanvas APIを利用可能にする
 */

import { vi } from 'vitest';

let createCanvas;
let createImageData;
try {
  // ESMでの動的インポート（Vitestでサポート）
  const canvas = await import('canvas');
  createCanvas = canvas.createCanvas;
  createImageData = canvas.createImageData;

  // グローバルなCanvas APIを設定
  global.HTMLCanvasElement = class HTMLCanvasElement {
    constructor() {
      this.width = 300;
      this.height = 150;
      this._canvas = createCanvas(this.width, this.height);
    }

    getContext(type) {
      if (type === '2d') {
        return this._canvas.getContext('2d');
      }
      return null;
    }

    toDataURL(type, quality) {
      const actualType = type ?? 'image/png';
      return this._canvas.toDataURL(actualType, quality);
    }

    toBlob(callback, type, quality) {
      const actualType = type ?? 'image/png';
      const dataURL = this.toDataURL(actualType, quality);
      const base64 = dataURL.split(',')[1];
      const binary = atob(base64);
      const array = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        array[i] = binary.charCodeAt(i);
      }
      const blob = new Blob([array], { type: actualType });
      callback(blob);
    }

    getBoundingClientRect() {
      return {
        top: 0,
        left: 0,
        bottom: this.height,
        right: this.width,
        width: this.width,
        height: this.height,
        x: 0,
        y: 0,
      };
    }
  };

  console.log('Successfully loaded @napi-rs/canvas for Vitest');
} catch (e) {
  console.warn('Failed to load @napi-rs/canvas, falling back to mock Canvas');

  // フォールバック用のモック（軽量版）
  global.HTMLCanvasElement = class HTMLCanvasElement {
    constructor() {
      this.width = 300;
      this.height = 150;
    }

    getContext(type) {
      if (type === '2d') {
        return {
          fillRect: vi.fn(),
          clearRect: vi.fn(),
          strokeRect: vi.fn(),
          fillStyle: '#000000',
          strokeStyle: '#000000',
          lineWidth: 1,
          globalAlpha: 1,
          beginPath: vi.fn(),
          moveTo: vi.fn(),
          lineTo: vi.fn(),
          stroke: vi.fn(),
          fill: vi.fn(),
          arc: vi.fn(),
          setLineDash: vi.fn(),
          scale: vi.fn(),
          save: vi.fn(),
          restore: vi.fn(),
          drawImage: vi.fn(),
          getImageData: vi.fn(() => ({
            data: new Uint8ClampedArray(this.width * this.height * 4),
          })),
          putImageData: vi.fn(),
          createImageData: vi.fn(() => ({
            data: new Uint8ClampedArray(4),
          })),
          font: '10px sans-serif',
          textAlign: 'start',
          textBaseline: 'alphabetic',
          fillText: vi.fn(),
          strokeText: vi.fn(),
          measureText: vi.fn(() => ({ width: 10 })),
          canvas: this,
        };
      }
      return null;
    }

    toDataURL() {
      return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
    }

    getBoundingClientRect() {
      return {
        top: 0,
        left: 0,
        bottom: this.height,
        right: this.width,
        width: this.width,
        height: this.height,
        x: 0,
        y: 0,
      };
    }
  };
}
