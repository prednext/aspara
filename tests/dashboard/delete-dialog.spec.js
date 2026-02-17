/**
 * Playwright tests for delete confirmation dialogs
 */

const { test, expect } = require('@playwright/test');

// Mock data setup helper
async function setupMockData(page) {
  // Mock the metrics reader API responses for testing
  await page.route('**/api/projects/**', async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    if (method === 'DELETE') {
      if (url.includes('/api/projects/test_project/runs/test_run')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            message: "Run 'test_project/test_run' deleted successfully",
          }),
        });
      } else if (url.includes('/api/projects/test_project')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ message: "Project 'test_project' deleted successfully" }),
        });
      }
    } else {
      // Handle GET requests with mock data
      if (url.endsWith('/projects/test_project')) {
        await route.fulfill({
          status: 200,
          contentType: 'text/html',
          body: `
            <html>
              <head><title>Test Runs</title></head>
              <body>
                <div id="notification-container" class="fixed top-20 left-1/2 transform -translate-x-1/2 z-50 space-y-2"></div>
                <div class="group bg-white border-b border-neutral-100 px-4 py-3">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center min-w-0 flex-1">
                      <span class="font-medium text-neutral-900 truncate">test_run</span>
                    </div>
                    <div class="flex items-center space-x-3 flex-shrink-0 ml-4">
                      <span class="text-sm text-neutral-500 whitespace-nowrap">January 15, 2024</span>
                      <button class="opacity-0 group-hover:opacity-100" onclick="deleteRun('test_project', 'test_run')" title="Delete run">Delete</button>
                    </div>
                  </div>
                </div>
                <script>
                  // Mock notification functions
                  window.showSuccessNotification = function(message) {
                    const container = document.getElementById('notification-container');
                    const notification = document.createElement('div');
                    notification.className = 'bg-green-50 text-green-800 border border-green-200 px-4 py-3 rounded';
                    notification.innerHTML = '<span>' + message + '</span><button>×</button>';
                    container.appendChild(notification);
                    setTimeout(() => notification.remove(), 5000);
                  };
                  window.showErrorNotification = function(message) {
                    const container = document.getElementById('notification-container');
                    const notification = document.createElement('div');
                    notification.className = 'bg-red-50 text-red-800 border border-red-200 px-4 py-3 rounded';
                    notification.innerHTML = '<span>' + message + '</span><button>×</button>';
                    container.appendChild(notification);
                  };
                  
                  window.deleteRun = async function(project, run) {
                    const confirmed = confirm('本当にラン "' + run + '" を削除しますか？\\nこの操作は取り消せません。');
                    if (confirmed) {
                      showSuccessNotification('削除が実行されました');
                    }
                  };
                </script>
              </body>
            </html>
          `,
        });
      } else if (url.endsWith('/')) {
        await route.fulfill({
          status: 200,
          contentType: 'text/html',
          body: `
            <html>
              <head><title>Test Projects</title></head>
              <body>
                <div id="notification-container" class="fixed top-20 left-1/2 transform -translate-x-1/2 z-50 space-y-2"></div>
                <div class="group bg-white p-4 mb-4">
                  <div class="flex items-center justify-between">
                    <div>
                      <h2>test_project</h2>
                    </div>
                    <div class="flex items-center space-x-2">
                      <button class="opacity-0 group-hover:opacity-100" onclick="deleteProject('test_project')" title="Delete project">Delete</button>
                    </div>
                  </div>
                </div>
                <script>
                  // Mock notification functions
                  window.showSuccessNotification = function(message) {
                    const container = document.getElementById('notification-container');
                    const notification = document.createElement('div');
                    notification.className = 'bg-green-50 text-green-800 border border-green-200 px-4 py-3 rounded';
                    notification.innerHTML = '<span>' + message + '</span><button>×</button>';
                    container.appendChild(notification);
                    // Auto-hide after 5 seconds
                    setTimeout(() => notification.remove(), 5000);
                  };
                  window.showErrorNotification = function(message) {
                    const container = document.getElementById('notification-container');
                    const notification = document.createElement('div');
                    notification.className = 'bg-red-50 text-red-800 border border-red-200 px-4 py-3 rounded';
                    notification.innerHTML = '<span>' + message + '</span><button>×</button>';
                    container.appendChild(notification);
                  };
                  
                  window.deleteProject = async function(project) {
                    const confirmed = confirm('本当にプロジェクト "' + project + '" を削除しますか？\\nこの操作は取り消せません。');
                    if (confirmed) {
                      showSuccessNotification('削除が実行されました');
                    }
                  };
                </script>
              </body>
            </html>
          `,
        });
      }
    }
  });
}

test.describe('Delete Dialog Tests', () => {
  test.beforeEach(async ({ page }) => {
    await setupMockData(page);
  });

  test('Project delete dialog shows confirmation', async ({ page }) => {
    await page.goto('/');

    // Set up dialog handler
    let dialogMessage = '';
    page.on('dialog', async (dialog) => {
      dialogMessage = dialog.message();
      await dialog.dismiss(); // Cancel the dialog
    });

    // Hover over the project item to reveal delete button
    await page.hover('.group');

    // Click delete button
    await page.click('button[title="Delete project"]');

    // Verify dialog appeared with correct message
    expect(dialogMessage).toContain('本当にプロジェクト "test_project" を削除しますか？');
    expect(dialogMessage).toContain('この操作は取り消せません。');
  });

  test('Project delete proceeds when confirmed', async ({ page }) => {
    await page.goto('/');

    // Set up dialog handler to accept
    page.on('dialog', async (dialog) => {
      await dialog.accept();
    });

    // Hover over the project item to reveal delete button
    await page.hover('.group');

    // Click delete button
    await page.click('button[title="Delete project"]');

    // Wait for notification to appear
    await page.waitForSelector('#notification-container .bg-green-50', { timeout: 2000 });

    // Verify success notification appeared
    const notification = await page.locator('#notification-container .bg-green-50').first();
    await expect(notification).toBeVisible();

    const notificationText = await notification.textContent();
    expect(notificationText).toContain('削除');
  });

  test('Run delete dialog shows confirmation', async ({ page }) => {
    await page.goto('/projects/test_project');

    let dialogMessage = '';
    page.on('dialog', async (dialog) => {
      dialogMessage = dialog.message();
      await dialog.dismiss();
    });

    await page.click('button[title="Delete run"]');

    expect(dialogMessage).toContain('本当にラン "test_run" を削除しますか？');
    expect(dialogMessage).toContain('この操作は取り消せません。');
  });

  test('Delete is cancelled when user clicks No', async ({ page }) => {
    await page.goto('/');

    page.on('dialog', async (dialog) => {
      await dialog.dismiss(); // Cancel confirmation
    });

    // Hover over the project item to reveal delete button
    await page.hover('.group');

    await page.click('button[title="Delete project"]');

    // Wait a bit to see if notification appears
    await page.waitForTimeout(500);

    // Notification should not have appeared since deletion was cancelled
    const notifications = await page.locator('#notification-container > div').count();
    expect(notifications).toBe(0);
  });

  test('Delete button prevents event bubbling', async ({ page }) => {
    await page.goto('/');

    let pageNavigated = false;
    page.on('framenavigated', () => {
      pageNavigated = true;
    });

    // Set up dialog handler to dismiss
    page.on('dialog', async (dialog) => {
      await dialog.dismiss();
    });

    // Hover over the project item to reveal delete button
    await page.hover('.group');

    // Click delete button - should not navigate to project page
    await page.click('button[title="Delete project"]');

    await page.waitForTimeout(100);

    // Page should not have navigated
    expect(pageNavigated).toBe(false);
  });

  test('Delete button is hidden by default and shown on hover', async ({ page }) => {
    await page.goto('/');

    // Delete button should be hidden initially
    const deleteButton = page.locator('button[title="Delete project"]');
    await expect(deleteButton).toHaveClass(/opacity-0/);

    // Hover over the project item
    await page.hover('.group');

    // Delete button should become visible
    await expect(deleteButton).toHaveClass(/group-hover:opacity-100/);
  });

  test('Delete button has gray color and rounded background on hover', async ({ page }) => {
    await page.goto('/');

    // Hover over the project item to reveal delete button
    await page.hover('.group');

    // Check delete button styling
    const deleteButton = page.locator('button[title="Delete project"]');
    await expect(deleteButton).toHaveClass(/text-neutral-400/);
    await expect(deleteButton).toHaveClass(/hover:text-neutral-600/);
    await expect(deleteButton).toHaveClass(/hover:bg-neutral-100/);
    await expect(deleteButton).toHaveClass(/rounded-md/);
  });
});

test.describe('Delete Function Error Handling', () => {
  test('Shows error notification when API returns error', async ({ page }) => {
    // Mock API to return error
    await page.route('**/api/projects/test_project', async (route) => {
      if (route.request().method() === 'DELETE') {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ detail: "Project 'test_project' does not exist" }),
        });
      }
    });

    await page.goto('/');

    page.on('dialog', async (dialog) => {
      await dialog.accept(); // Accept confirmation
    });

    // Hover over the project item to reveal delete button
    await page.hover('.group');

    await page.click('button[title="Delete project"]');

    // Wait for error notification
    await page.waitForSelector('#notification-container .bg-red-50', { timeout: 2000 });

    const errorNotification = await page.locator('#notification-container .bg-red-50').first();
    await expect(errorNotification).toBeVisible();

    const notificationText = await errorNotification.textContent();
    expect(notificationText).toContain('削除に失敗しました');
    expect(notificationText).toContain('does not exist');
  });

  test('Shows network error notification', async ({ page }) => {
    // Mock network failure
    await page.route('**/api/projects/test_project', async (route) => {
      if (route.request().method() === 'DELETE') {
        await route.abort('failed');
      }
    });

    await page.goto('/');

    page.on('dialog', async (dialog) => {
      await dialog.accept(); // Accept confirmation
    });

    // Hover over the project item to reveal delete button
    await page.hover('.group');

    await page.click('button[title="Delete project"]');

    // Wait for error notification
    await page.waitForSelector('#notification-container .bg-red-50', { timeout: 2000 });

    const errorNotification = await page.locator('#notification-container .bg-red-50').first();
    await expect(errorNotification).toBeVisible();

    const notificationText = await errorNotification.textContent();
    expect(notificationText).toContain('削除中にエラーが発生しました');
  });

  test('Notification auto-hides after duration', async ({ page }) => {
    await page.goto('/');

    page.on('dialog', async (dialog) => {
      await dialog.accept(); // Accept confirmation
    });

    // Hover over the project item to reveal delete button
    await page.hover('.group');

    await page.click('button[title="Delete project"]');

    // Wait for success notification
    await page.waitForSelector('#notification-container .bg-green-50', { timeout: 2000 });

    const notification = await page.locator('#notification-container .bg-green-50').first();
    await expect(notification).toBeVisible();

    // Wait for notification to auto-hide (success notifications auto-hide after 5 seconds)
    await page.waitForTimeout(6000);

    // Notification should be gone or hidden
    await expect(notification).not.toBeVisible();
  });

  test('Notification can be manually closed', async ({ page }) => {
    await page.goto('/');

    page.on('dialog', async (dialog) => {
      await dialog.accept(); // Accept confirmation
    });

    // Hover over the project item to reveal delete button
    await page.hover('.group');

    await page.click('button[title="Delete project"]');

    // Wait for success notification
    await page.waitForSelector('#notification-container .bg-green-50', { timeout: 2000 });

    const notification = await page.locator('#notification-container .bg-green-50').first();
    await expect(notification).toBeVisible();

    // Click close button
    const closeButton = notification.locator('button');
    await closeButton.click();

    // Notification should be gone
    await expect(notification).not.toBeVisible();
  });
});
