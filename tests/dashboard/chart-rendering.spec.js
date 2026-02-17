import { expect, test } from '../fixtures.js';

test.describe('Chart Rendering - Regression Prevention', () => {
  test.beforeEach(async ({ page, port }) => {
    console.log(`Running test with server on port ${port}`);
    // Listen for console errors
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        console.error('Browser console error:', msg.text());
      }
    });

    // Listen for page errors
    page.on('pageerror', (error) => {
      console.error('Page error:', error.message);
    });
  });

  test('charts must render immediately on page load (not only on hover)', async ({ page }) => {
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));

    await page.goto('/projects/default');

    // Wait for charts container to be visible
    await page.waitForSelector('#chartsContainer:not(.hidden)', { timeout: 5000 });

    // Get first canvas
    const canvas = page.locator('#chartsContainer canvas').first();
    await expect(canvas).toBeVisible({ timeout: 2000 });

    // CRITICAL: Check that canvas has actual content BEFORE any interaction
    // This detects the "only shows on hover" bug
    const hasContentBeforeHover = await canvas.evaluate((canvasEl) => {
      const ctx = canvasEl.getContext('2d');
      const imageData = ctx.getImageData(0, 0, canvasEl.width, canvasEl.height);
      const data = imageData.data;

      // Check if there are non-white pixels (actual chart content)
      for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];

        // If not white (255, 255, 255), we have content
        if (r !== 255 || g !== 255 || b !== 255) {
          return true;
        }
      }
      return false;
    });

    // Chart MUST have content before any user interaction
    expect(hasContentBeforeHover).toBe(true);

    // Verify no JavaScript errors occurred
    expect(errors).toEqual([]);
  });

  test('charts must not disappear after initial render', async ({ page }) => {
    await page.goto('/projects/default');
    await page.waitForSelector('#chartsContainer canvas', { timeout: 5000 });

    const canvas = page.locator('#chartsContainer canvas').first();

    // Take screenshot immediately
    const screenshot1 = await canvas.screenshot();

    // Wait 1 second to catch "appears then disappears" bug
    await page.waitForTimeout(1000);

    // Canvas should still be visible
    await expect(canvas).toBeVisible();

    // Check it still has content
    const hasContent = await canvas.evaluate((canvasEl) => {
      const ctx = canvasEl.getContext('2d');
      const imageData = ctx.getImageData(0, 0, canvasEl.width, canvasEl.height);
      const data = imageData.data;

      for (let i = 0; i < data.length; i += 4) {
        if (data[i] !== 255 || data[i + 1] !== 255 || data[i + 2] !== 255) {
          return true;
        }
      }
      return false;
    });

    expect(hasContent).toBe(true);
  });

  test('no JavaScript errors should occur during chart rendering', async ({ page }) => {
    const consoleErrors = [];
    const pageErrors = [];

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    page.on('pageerror', (error) => {
      pageErrors.push(error.message);
    });

    await page.goto('/projects/default');
    await page.waitForSelector('#chartsContainer canvas', { timeout: 5000 });

    // Wait a bit for any delayed errors
    await page.waitForTimeout(500);

    // Should have no errors
    expect(consoleErrors).toEqual([]);
    expect(pageErrors).toEqual([]);
  });

  test('changing chart size should not break rendering', async ({ page }) => {
    await page.goto('/projects/default');
    await page.waitForSelector('#chartsContainer canvas', { timeout: 5000 });

    const canvas = page.locator('#chartsContainer canvas').first();

    // Change size to Large
    await page.click('#sizeL');
    await page.waitForTimeout(300);

    // Must still be visible and have content
    await expect(canvas).toBeVisible();

    const hasContent = await canvas.evaluate((canvasEl) => {
      const ctx = canvasEl.getContext('2d');
      const imageData = ctx.getImageData(0, 0, canvasEl.width, canvasEl.height);
      const data = imageData.data;

      for (let i = 0; i < data.length; i += 4) {
        if (data[i] !== 255 || data[i + 1] !== 255 || data[i + 2] !== 255) {
          return true;
        }
      }
      return false;
    });

    expect(hasContent).toBe(true);
  });
});
