/**
 * E2E tests for tag editing functionality on actual dashboard pages
 * Tests the integration of tag editor with projects and runs list pages
 */

const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');
const os = require('os');

test.describe('Tag Editing Integration', () => {
  let testDataDir;
  let serverProcess;
  let serverUrl;

  test.beforeAll(async () => {
    // Create temporary data directory
    testDataDir = path.join(os.tmpdir(), `aspara-tag-test-${Date.now()}`);
    fs.mkdirSync(testDataDir, { recursive: true });

    // Create test project and run with some initial tags
    const projectDir = path.join(testDataDir, 'test_project');
    fs.mkdirSync(projectDir, { recursive: true });

    // Create run JSONL file
    const runFile = path.join(projectDir, 'test_run.jsonl');
    const initRecord = {
      type: 'init',
      timestamp: new Date().toISOString(),
      run: 'test_run',
      run_id: 'test-run-id-123',
      project: 'test_project',
      tags: ['initial-tag-1', 'initial-tag-2'],
      notes: '',
    };
    const metricRecord = {
      type: 'metrics',
      timestamp: new Date().toISOString(),
      run: 'test_run',
      project: 'test_project',
      step: 0,
      metrics: { loss: 0.5 },
    };
    fs.writeFileSync(runFile, JSON.stringify(initRecord) + '\n' + JSON.stringify(metricRecord) + '\n');

    // Create metadata file with project tags
    const metadataFile = path.join(projectDir, '.project.meta.json');
    const metadata = {
      notes: '',
      tags: ['project-tag-1', 'project-tag-2'],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    fs.writeFileSync(metadataFile, JSON.stringify(metadata));

    // Start dashboard server
    const { spawn } = require('child_process');
    serverProcess = spawn('uv', ['run', 'aspara', 'dashboard', '--port', '0'], {
      env: { ...process.env, ASPARA_DATA_DIR: testDataDir },
    });

    // Wait for server to start and capture the port
    await new Promise((resolve, reject) => {
      let output = '';
      const timeout = setTimeout(() => {
        reject(new Error('Server failed to start within timeout'));
      }, 15000);

      const checkOutput = (data) => {
        output += data.toString();
        const match = output.match(/Uvicorn running on http:\/\/127\.0\.0\.1:(\d+)/);
        if (match) {
          clearTimeout(timeout);
          serverUrl = `http://localhost:${match[1]}`;
          resolve();
        }
      };

      serverProcess.stdout.on('data', checkOutput);
      serverProcess.stderr.on('data', checkOutput);

      serverProcess.on('error', (error) => {
        clearTimeout(timeout);
        reject(error);
      });
    });
  });

  test.afterAll(async () => {
    // Stop server
    if (serverProcess) {
      serverProcess.kill();
    }

    // Clean up test data
    if (testDataDir && fs.existsSync(testDataDir)) {
      fs.rmSync(testDataDir, { recursive: true, force: true });
    }
  });

  test.describe('Projects List Page', () => {
    test('should display project tags', async ({ page }) => {
      await page.goto(serverUrl);

      // Wait for projects to load
      await page.waitForSelector('[data-project="test_project"]');

      // Check that tags are displayed
      const projectCard = page.locator('[data-project="test_project"]');
      await expect(projectCard).toContainText('project-tag-1');
      await expect(projectCard).toContainText('project-tag-2');
    });

    test('should open tag editor without navigating when Edit button is clicked', async ({ page }) => {
      await page.goto(serverUrl);
      await page.waitForSelector('[data-project="test_project"]');

      // Find the tag container for test_project
      const tagContainer = page.locator('#project-tags-test_project');

      // Click Edit button
      const editBtn = tagContainer.locator('.tag-edit-btn');
      await editBtn.click();

      // Tag editor should be visible
      await expect(page.locator('.tag-edit')).toBeVisible();
      await expect(page.locator('.tag-input')).toBeVisible();

      // URL should not have changed (no navigation occurred)
      expect(page.url()).toBe(`${serverUrl}/`);
    });

    test('should not navigate when clicking inside tag editor area', async ({ page }) => {
      await page.goto(serverUrl);
      await page.waitForSelector('[data-project="test_project"]');

      const tagContainer = page.locator('#project-tags-test_project');

      // Click directly on tag container
      await tagContainer.click();

      // Should not navigate to project detail page
      expect(page.url()).toBe(`${serverUrl}/`);
    });

    test('should add tag without navigation', async ({ page }) => {
      await page.goto(serverUrl);
      await page.waitForSelector('[data-project="test_project"]');

      const tagContainer = page.locator('#project-tags-test_project');
      const editBtn = tagContainer.locator('.tag-edit-btn');
      await editBtn.click();

      // Type new tag and press Enter
      const input = page.locator('.tag-input');
      await input.fill('new-project-tag');
      await input.press('Enter');

      // Tag should appear in edit list
      await expect(page.locator('.tag-list-edit')).toContainText('new-project-tag');

      // URL should not have changed
      expect(page.url()).toBe(`${serverUrl}/`);
    });

    test('should save tags without navigation', async ({ page }) => {
      await page.goto(serverUrl);
      await page.waitForSelector('[data-project="test_project"]');

      const tagContainer = page.locator('#project-tags-test_project');
      const editBtn = tagContainer.locator('.tag-edit-btn');
      await editBtn.click();

      // Add a tag
      const input = page.locator('.tag-input');
      await input.fill('saved-tag');
      await input.press('Enter');

      // Click Save button
      const saveBtn = page.locator('.tag-save-btn');
      await saveBtn.click();

      // Wait for save to complete
      await expect(page.locator('.tag-edit')).toBeHidden();

      // New tag should be visible in display mode
      await expect(tagContainer).toContainText('saved-tag');

      // URL should not have changed
      expect(page.url()).toBe(`${serverUrl}/`);
    });

    test('should cancel without navigation', async ({ page }) => {
      await page.goto(serverUrl);
      await page.waitForSelector('[data-project="test_project"]');

      const tagContainer = page.locator('#project-tags-test_project');
      const editBtn = tagContainer.locator('.tag-edit-btn');
      await editBtn.click();

      // Add a tag
      const input = page.locator('.tag-input');
      await input.fill('temp-tag');
      await input.press('Enter');

      // Press Escape to cancel
      await input.press('Escape');

      // Edit mode should be closed
      await expect(page.locator('.tag-edit')).toBeHidden();

      // Temp tag should not be saved
      await expect(tagContainer).not.toContainText('temp-tag');

      // URL should not have changed
      expect(page.url()).toBe(`${serverUrl}/`);
    });

    test('should save with Ctrl+Enter without navigation', async ({ page }) => {
      await page.goto(serverUrl);
      await page.waitForSelector('[data-project="test_project"]');

      const tagContainer = page.locator('#project-tags-test_project');
      const editBtn = tagContainer.locator('.tag-edit-btn');
      await editBtn.click();

      // Add a tag
      const input = page.locator('.tag-input');
      await input.fill('ctrl-enter-tag');
      await input.press('Enter');

      // Press Ctrl+Enter to save
      await input.press('Control+Enter');

      // Wait for save to complete
      await expect(page.locator('.tag-edit')).toBeHidden();

      // URL should not have changed
      expect(page.url()).toBe(`${serverUrl}/`);
    });
  });

  test.describe('Runs List Page', () => {
    test('should display run tags', async ({ page }) => {
      await page.goto(`${serverUrl}/projects/test_project/runs`);

      // Wait for runs to load
      await page.waitForSelector('[data-run="test_run"]');

      // Check that tags are displayed
      const runCard = page.locator('[data-run="test_run"]');
      await expect(runCard).toContainText('initial-tag-1');
      await expect(runCard).toContainText('initial-tag-2');
    });

    test('should open tag editor without navigating when Edit button is clicked', async ({ page }) => {
      await page.goto(`${serverUrl}/projects/test_project/runs`);
      await page.waitForSelector('[data-run="test_run"]');

      // Find the tag container for test_run
      const tagContainer = page.locator('#run-tags-test_project-test_run');

      // Click Edit button
      const editBtn = tagContainer.locator('.tag-edit-btn');
      await editBtn.click();

      // Tag editor should be visible
      await expect(page.locator('.tag-edit')).toBeVisible();
      await expect(page.locator('.tag-input')).toBeVisible();

      // URL should not have changed (no navigation occurred)
      expect(page.url()).toBe(`${serverUrl}/projects/test_project/runs`);
    });

    test('should not navigate when clicking inside tag editor area', async ({ page }) => {
      await page.goto(`${serverUrl}/projects/test_project/runs`);
      await page.waitForSelector('[data-run="test_run"]');

      const tagContainer = page.locator('#run-tags-test_project-test_run');

      // Click directly on tag container
      await tagContainer.click();

      // Should not navigate to run detail page
      expect(page.url()).toBe(`${serverUrl}/projects/test_project/runs`);
    });

    test('should add tag without navigation', async ({ page }) => {
      await page.goto(`${serverUrl}/projects/test_project/runs`);
      await page.waitForSelector('[data-run="test_run"]');

      const tagContainer = page.locator('#run-tags-test_project-test_run');
      const editBtn = tagContainer.locator('.tag-edit-btn');
      await editBtn.click();

      // Type new tag and press Enter
      const input = page.locator('.tag-input');
      await input.fill('new-run-tag');
      await input.press('Enter');

      // Tag should appear in edit list
      await expect(page.locator('.tag-list-edit')).toContainText('new-run-tag');

      // URL should not have changed
      expect(page.url()).toBe(`${serverUrl}/projects/test_project/runs`);
    });

    test('should handle all keyboard shortcuts without navigation', async ({ page }) => {
      await page.goto(`${serverUrl}/projects/test_project/runs`);
      await page.waitForSelector('[data-run="test_run"]');

      const tagContainer = page.locator('#run-tags-test_project-test_run');
      const editBtn = tagContainer.locator('.tag-edit-btn');
      await editBtn.click();

      const input = page.locator('.tag-input');

      // Test Enter key (add tag)
      await input.fill('tag-from-enter');
      await input.press('Enter');
      expect(page.url()).toBe(`${serverUrl}/projects/test_project/runs`);

      // Test typing in input (should not navigate)
      await input.fill('typing test');
      expect(page.url()).toBe(`${serverUrl}/projects/test_project/runs`);

      // Test Escape key (cancel)
      await input.press('Escape');
      expect(page.url()).toBe(`${serverUrl}/projects/test_project/runs`);
    });

    test('should remove tag without navigation', async ({ page }) => {
      await page.goto(`${serverUrl}/projects/test_project/runs`);
      await page.waitForSelector('[data-run="test_run"]');

      const tagContainer = page.locator('#run-tags-test_project-test_run');
      const editBtn = tagContainer.locator('.tag-edit-btn');
      await editBtn.click();

      // Click remove button on first tag
      const removeBtn = page.locator('.tag-remove-btn').first();
      await removeBtn.click();

      // Tag should be removed from edit list
      await expect(page.locator('.tag-list-edit')).not.toContainText('initial-tag-1');

      // URL should not have changed
      expect(page.url()).toBe(`${serverUrl}/projects/test_project/runs`);
    });
  });

  test.describe('Multiple Tag Editors', () => {
    test('should only open clicked editor, not all editors', async ({ page }) => {
      // This test requires multiple runs, so we'll create another one
      const projectDir = path.join(testDataDir, 'test_project');
      const runFile2 = path.join(projectDir, 'test_run_2.jsonl');
      const initRecord2 = {
        type: 'init',
        timestamp: new Date().toISOString(),
        run: 'test_run_2',
        run_id: 'test-run-id-456',
        project: 'test_project',
        tags: ['run2-tag'],
        notes: '',
      };
      fs.writeFileSync(runFile2, JSON.stringify(initRecord2) + '\n');

      await page.goto(`${serverUrl}/projects/test_project/runs`);
      await page.waitForSelector('[data-run="test_run"]');
      await page.waitForSelector('[data-run="test_run_2"]');

      // Click Edit button on first run
      const tagContainer1 = page.locator('#run-tags-test_project-test_run');
      const editBtn1 = tagContainer1.locator('.tag-edit-btn');
      await editBtn1.click();

      // Only the first editor should be open
      const editSections = page.locator('.tag-edit:not(.hidden)');
      await expect(editSections).toHaveCount(1);

      // Second run's editor should still be hidden
      const tagContainer2 = page.locator('#run-tags-test_project-test_run_2');
      const editSection2 = tagContainer2.locator('+ .tag-editor-wrapper .tag-edit');
      await expect(editSection2).toBeHidden();
    });
  });
});
