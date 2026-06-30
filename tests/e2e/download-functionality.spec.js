/**
 * E2E tests for chart download functionality
 * Tests actual user operations in a real browser
 */

import fs from 'node:fs';
import path from 'node:path';
import { expect, test } from '@playwright/test';

// TODO: E2E tests need to be rewritten to match the actual UI structure
test.describe.skip('Chart Download E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Clear the download folder
    const downloadPath = path.join(process.cwd(), 'test-downloads');
    if (fs.existsSync(downloadPath)) {
      fs.rmSync(downloadPath, { recursive: true });
    }
    fs.mkdirSync(downloadPath, { recursive: true });
  });

  test.describe('Run Detail Chart Downloads', () => {
    test('should download CSV data from run detail chart', async ({ page }) => {
      // Navigate to the run detail page
      await page.goto('/projects/default/runs/test_run');

      // Wait for the chart to load
      await page.waitForSelector('.metric-chart', { timeout: 10000 });

      // Find the download button on the first chart
      const firstChart = page.locator('.metric-chart').first();
      const downloadButton = firstChart.locator('button[title="Download data"]');

      // Verify the download button is visible
      await expect(downloadButton).toBeVisible();

      // Open the download menu
      await downloadButton.click();

      // Select CSV format
      const downloadPromise = page.waitForDownload();
      await page.click('text=CSV形式');

      const download = await downloadPromise;

      // Verify the downloaded file
      expect(download.suggestedFilename()).toMatch(/\.csv$/);

      // Verify the contents of the downloaded file
      const downloadPath = path.join(process.cwd(), 'test-downloads', download.suggestedFilename());
      await download.saveAs(downloadPath);

      const csvContent = fs.readFileSync(downloadPath, 'utf8');
      expect(csvContent).toContain('series,step,value');
      expect(csvContent.split('\n').length).toBeGreaterThan(1); // has data beyond the header
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

      // Verify the SVG file contents
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

      // Verify the PNG file size (confirm it is not 0 bytes)
      const downloadPath = path.join(process.cwd(), 'test-downloads', download.suggestedFilename());
      await download.saveAs(downloadPath);

      const stats = fs.statSync(downloadPath);
      expect(stats.size).toBeGreaterThan(0);
    });
  });

  test.describe('Compare Runs Chart Downloads', () => {
    test('should download multi-run comparison as CSV', async ({ page }) => {
      await page.goto('/projects/default');

      // Select runs
      await page.check('[data-run-name="run_1"]');
      await page.check('[data-run-name="run_2"]');

      // Click the compare button
      await page.click('#compareButton');

      // Wait for the comparison chart to appear
      await page.waitForSelector('.chart-container');

      // Download button on the first comparison chart
      const firstChart = page.locator('.chart-container').first();
      const downloadButton = firstChart.locator('button[title="Download data"]');

      await downloadButton.click();

      const downloadPromise = page.waitForDownload();
      await page.click('text=CSV形式');

      const download = await downloadPromise;

      expect(download.suggestedFilename()).toMatch(/\.csv$/);

      // Verify multi-run data
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

      // Zoom the chart (simulate a drag operation)
      const canvasBox = await canvas.boundingBox();
      await page.mouse.move(canvasBox.x + 50, canvasBox.y + 50);
      await page.mouse.down();
      await page.mouse.move(canvasBox.x + 200, canvasBox.y + 150);
      await page.mouse.up();

      // Download after zooming
      const downloadButton = firstChart.locator('button[title="Download data"]');
      await downloadButton.click();

      const downloadPromise = page.waitForDownload();
      await page.click('text=SVG画像');

      const download = await downloadPromise;

      // Verify the filename contains "_zoomed"
      expect(download.suggestedFilename()).toContain('_zoomed');
      expect(download.suggestedFilename()).toMatch(/\.svg$/);
    });
  });

  test.describe('Download Error Handling', () => {
    test('should handle download when no data is available', async ({ page }) => {
      // Simulate a run detail page with no data
      await page.goto('/projects/default/runs/empty_run');

      // Verify an error message or "no data" message is shown
      await expect(page.locator('text=メトリクスが記録されていません')).toBeVisible({ timeout: 10000 });
    });

    test('should handle network errors gracefully', async ({ page }) => {
      // Simulate a network error
      await page.route('/api/dashboard/**', (route) => {
        route.abort('failed');
      });

      await page.goto('/projects/default/runs/test_run');

      // Verify an error message is shown
      await expect(page.locator('text=エラーが発生しました')).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Download UI Interaction', () => {
    test('should show and hide download menu correctly', async ({ page }) => {
      await page.goto('/projects/default/runs/test_run');
      await page.waitForSelector('.metric-chart');

      const firstChart = page.locator('.metric-chart').first();
      const downloadButton = firstChart.locator('button[title="Download data"]');

      // Menu is hidden in the initial state
      const downloadMenu = firstChart.locator('.download-menu');
      await expect(downloadMenu).toBeHidden();

      // Clicking the button shows the menu
      await downloadButton.click();
      await expect(downloadMenu).toBeVisible();

      // Clicking outside the menu hides it
      await page.click('body');
      await expect(downloadMenu).toBeHidden();
    });

    test('should have correct menu options', async ({ page }) => {
      await page.goto('/projects/default/runs/test_run');
      await page.waitForSelector('.metric-chart');

      const firstChart = page.locator('.metric-chart').first();
      const downloadButton = firstChart.locator('button[title="Download data"]');

      await downloadButton.click();

      // Verify menu options
      await expect(page.locator('text=CSV形式')).toBeVisible();
      await expect(page.locator('text=SVG画像')).toBeVisible();
      await expect(page.locator('text=PNG画像')).toBeVisible();
    });
  });
});
