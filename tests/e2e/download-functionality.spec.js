/**
 * チャートダウンロード機能のE2Eテスト
 * 実ブラウザでの実際のユーザー操作をテスト
 */

import fs from 'node:fs';
import path from 'node:path';
import { expect, test } from '@playwright/test';

// TODO: E2Eテストを実際のUI構造に合わせて書き直す必要がある
test.describe.skip('Chart Download E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // ダウンロードフォルダをクリア
    const downloadPath = path.join(process.cwd(), 'test-downloads');
    if (fs.existsSync(downloadPath)) {
      fs.rmSync(downloadPath, { recursive: true });
    }
    fs.mkdirSync(downloadPath, { recursive: true });
  });

  test.describe('Run Detail Chart Downloads', () => {
    test('should download CSV data from run detail chart', async ({ page }) => {
      // run detail画面に移動
      await page.goto('/projects/default/runs/test_run');

      // チャートが読み込まれるまで待機
      await page.waitForSelector('.metric-chart', { timeout: 10000 });

      // 最初のチャートのダウンロードボタンを探す
      const firstChart = page.locator('.metric-chart').first();
      const downloadButton = firstChart.locator('button[title="Download data"]');

      // ダウンロードボタンが表示されることを確認
      await expect(downloadButton).toBeVisible();

      // ダウンロードメニューを開く
      await downloadButton.click();

      // CSV形式を選択
      const downloadPromise = page.waitForDownload();
      await page.click('text=CSV形式');

      const download = await downloadPromise;

      // ダウンロードファイルの確認
      expect(download.suggestedFilename()).toMatch(/\.csv$/);

      // ダウンロードファイルの内容を確認
      const downloadPath = path.join(process.cwd(), 'test-downloads', download.suggestedFilename());
      await download.saveAs(downloadPath);

      const csvContent = fs.readFileSync(downloadPath, 'utf8');
      expect(csvContent).toContain('series,step,value');
      expect(csvContent.split('\n').length).toBeGreaterThan(1); // ヘッダー以外のデータがある
    });

    test('should download SVG image from run detail chart', async ({ page }) => {
      await page.goto('/projects/default/runs/test_run');
      await page.waitForSelector('.metric-chart');

      const firstChart = page.locator('.metric-chart').first();
      const downloadButton = firstChart.locator('button[title="Download data"]');

      await downloadButton.click();

      const downloadPromise = page.waitForDownload();
      await page.click('text=SVG画像');

      const download = await downloadPromise;

      expect(download.suggestedFilename()).toMatch(/\.svg$/);

      // SVGファイルの内容確認
      const downloadPath = path.join(process.cwd(), 'test-downloads', download.suggestedFilename());
      await download.saveAs(downloadPath);

      const svgContent = fs.readFileSync(downloadPath, 'utf8');
      expect(svgContent).toContain('<svg');
      expect(svgContent).toContain('</svg>');
    });

    test('should download PNG image from run detail chart', async ({ page }) => {
      await page.goto('/projects/default/runs/test_run');
      await page.waitForSelector('.metric-chart');

      const firstChart = page.locator('.metric-chart').first();
      const downloadButton = firstChart.locator('button[title="Download data"]');

      await downloadButton.click();

      const downloadPromise = page.waitForDownload();
      await page.click('text=PNG画像');

      const download = await downloadPromise;

      expect(download.suggestedFilename()).toMatch(/\.png$/);

      // PNGファイルのサイズ確認（0バイトでないことを確認）
      const downloadPath = path.join(process.cwd(), 'test-downloads', download.suggestedFilename());
      await download.saveAs(downloadPath);

      const stats = fs.statSync(downloadPath);
      expect(stats.size).toBeGreaterThan(0);
    });
  });

  test.describe('Compare Runs Chart Downloads', () => {
    test('should download multi-run comparison as CSV', async ({ page }) => {
      await page.goto('/projects/default');

      // ランを選択
      await page.check('[data-run-name="run_1"]');
      await page.check('[data-run-name="run_2"]');

      // 比較ボタンをクリック
      await page.click('#compareButton');

      // 比較チャートが表示されるまで待機
      await page.waitForSelector('.chart-container');

      // 最初の比較チャートのダウンロードボタン
      const firstChart = page.locator('.chart-container').first();
      const downloadButton = firstChart.locator('button[title="Download data"]');

      await downloadButton.click();

      const downloadPromise = page.waitForDownload();
      await page.click('text=CSV形式');

      const download = await downloadPromise;

      expect(download.suggestedFilename()).toMatch(/\.csv$/);

      // マルチランデータの確認
      const downloadPath = path.join(process.cwd(), 'test-downloads', download.suggestedFilename());
      await download.saveAs(downloadPath);

      const csvContent = fs.readFileSync(downloadPath, 'utf8');
      expect(csvContent).toContain('series,step,value');
      expect(csvContent).toContain('run_1');
      expect(csvContent).toContain('run_2');
    });

    test('should download comparison chart as PNG', async ({ page }) => {
      await page.goto('/projects/default');

      await page.check('[data-run-name="run_1"]');
      await page.check('[data-run-name="run_2"]');
      await page.click('#compareButton');

      await page.waitForSelector('.chart-container');

      const firstChart = page.locator('.chart-container').first();
      const downloadButton = firstChart.locator('button[title="Download data"]');

      await downloadButton.click();

      const downloadPromise = page.waitForDownload();
      await page.click('text=PNG画像');

      const download = await downloadPromise;

      expect(download.suggestedFilename()).toMatch(/\.png$/);
    });
  });

  test.describe('Chart Zoom and Download', () => {
    test('should download zoomed chart with "_zoomed" suffix', async ({ page }) => {
      await page.goto('/projects/default/runs/test_run');
      await page.waitForSelector('.metric-chart');

      const firstChart = page.locator('.metric-chart').first();
      const canvas = firstChart.locator('canvas');

      // チャートをズーム（ドラッグ操作をシミュレート）
      const canvasBox = await canvas.boundingBox();
      await page.mouse.move(canvasBox.x + 50, canvasBox.y + 50);
      await page.mouse.down();
      await page.mouse.move(canvasBox.x + 200, canvasBox.y + 150);
      await page.mouse.up();

      // ズーム後にダウンロード
      const downloadButton = firstChart.locator('button[title="Download data"]');
      await downloadButton.click();

      const downloadPromise = page.waitForDownload();
      await page.click('text=SVG画像');

      const download = await downloadPromise;

      // ファイル名に"_zoomed"が含まれることを確認
      expect(download.suggestedFilename()).toContain('_zoomed');
      expect(download.suggestedFilename()).toMatch(/\.svg$/);
    });
  });

  test.describe('Download Error Handling', () => {
    test('should handle download when no data is available', async ({ page }) => {
      // データのないrun detail画面をシミュレート
      await page.goto('/projects/default/runs/empty_run');

      // エラーメッセージまたは"データなし"メッセージが表示されることを確認
      await expect(page.locator('text=メトリクスが記録されていません')).toBeVisible({ timeout: 10000 });
    });

    test('should handle network errors gracefully', async ({ page }) => {
      // ネットワークエラーをシミュレート
      await page.route('/api/dashboard/**', (route) => {
        route.abort('failed');
      });

      await page.goto('/projects/default/runs/test_run');

      // エラーメッセージが表示されることを確認
      await expect(page.locator('text=エラーが発生しました')).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Download UI Interaction', () => {
    test('should show and hide download menu correctly', async ({ page }) => {
      await page.goto('/projects/default/runs/test_run');
      await page.waitForSelector('.metric-chart');

      const firstChart = page.locator('.metric-chart').first();
      const downloadButton = firstChart.locator('button[title="Download data"]');

      // メニューが初期状態では非表示
      const downloadMenu = firstChart.locator('.download-menu');
      await expect(downloadMenu).toBeHidden();

      // ボタンクリックでメニューが表示
      await downloadButton.click();
      await expect(downloadMenu).toBeVisible();

      // メニュー外クリックで非表示
      await page.click('body');
      await expect(downloadMenu).toBeHidden();
    });

    test('should have correct menu options', async ({ page }) => {
      await page.goto('/projects/default/runs/test_run');
      await page.waitForSelector('.metric-chart');

      const firstChart = page.locator('.metric-chart').first();
      const downloadButton = firstChart.locator('button[title="Download data"]');

      await downloadButton.click();

      // メニューオプションの確認
      await expect(page.locator('text=CSV形式')).toBeVisible();
      await expect(page.locator('text=SVG画像')).toBeVisible();
      await expect(page.locator('text=PNG画像')).toBeVisible();
    });
  });
});
