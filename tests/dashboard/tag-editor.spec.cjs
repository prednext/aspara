/**
 * Playwright tests for tag editor UI functionality
 */

const { test, expect } = require('@playwright/test');

test.describe('Tag Editor UI', () => {
  test.beforeEach(async ({ page }) => {
    // Mock API responses
    await page.route('/api/projects/test_project/metadata', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            notes: '',
            tags: ['tag1', 'tag2'],
            created_at: null,
            updated_at: null,
          }),
        });
      } else if (route.request().method() === 'PUT') {
        const postData = route.request().postDataJSON();
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            notes: postData.notes || '',
            tags: postData.tags || [],
            created_at: '2026-01-04T10:00:00',
            updated_at: '2026-01-04T10:00:00',
          }),
        });
      }
    });

    // Set up a test page with tag editor
    await page.setContent(`
      <!DOCTYPE html>
      <html>
      <head>
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
          tailwind.config = {
            theme: {
              extend: {
                colors: {
                  'action': '#111827',
                  'action-hover': '#1f2937',
                  'secondary': '#6b7280',
                  'secondary-hover': '#4b5563',
                  'accent': '#64748b',
                  'accent-hover': '#475569',
                  'base-bg': '#fafafa',
                  'base-border': '#e5e7eb',
                  'base-surface': '#ffffff',
                  'text-primary': '#111827',
                  'text-secondary': '#6b7280',
                  'text-muted': '#9ca3af',
                  'status-error': '#dc2626',
                },
                borderRadius: {
                  'button': '6px',
                }
              }
            }
          }
        </script>
      </head>
      <body>
        <div id="test-tags"></div>
        <script type="module">
          function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
          }

          class TagEditor {
            constructor() {
              this.isEditing = false;
              this.originalTags = [];
              this.currentTags = [];
              this.currentElement = null;
              this.currentApiEndpoint = null;
            }

            init(element, apiEndpoint, currentTags = []) {
              if (!element || !apiEndpoint) return;

              const wrapper = this.createTagWrapper(element, currentTags);
              element.parentNode.replaceChild(wrapper, element);

              this.attachEventListeners(wrapper, apiEndpoint);
            }

            createTagWrapper(originalElement, tags) {
              const wrapper = document.createElement('div');
              wrapper.className = 'tag-editor-wrapper';

              const display = document.createElement('div');
              display.className = 'tag-display flex items-center gap-2 flex-wrap';

              const tagsHtml = tags.length > 0
                ? tags.map(tag => \`<span class="inline-flex items-center px-2 py-0.5 rounded-full bg-base-bg text-xs text-text-muted border border-base-border">\${escapeHtml(tag)}</span>\`).join('')
                : '<span class="text-text-muted italic text-sm">No tags</span>';

              display.innerHTML = \`
                <div class="tag-list flex items-center gap-1.5 flex-wrap">\${tagsHtml}</div>
              \`;

              const editBtn = document.createElement('button');
              editBtn.className = 'tag-edit-btn px-2 py-1 text-sm text-accent hover:text-accent-hover transition-colors';
              editBtn.innerHTML = 'Edit';
              display.appendChild(editBtn);

              const edit = document.createElement('div');
              edit.className = 'tag-edit hidden';
              edit.innerHTML = \`
                <div class="mb-3">
                  <div class="flex gap-2 mb-2">
                    <input type="text"
                           class="tag-input flex-1 px-3 py-1.5 border border-base-border rounded focus:outline-none focus:ring-2 focus:ring-accent text-sm"
                           placeholder="Add tag (press Enter)"
                           maxlength="50">
                    <button class="tag-add-btn px-3 py-1.5 text-sm bg-action text-white rounded-button hover:bg-action-hover transition-colors">
                      Add
                    </button>
                  </div>
                  <div class="tag-list-edit flex flex-wrap gap-1.5"></div>
                </div>
                <div class="tag-actions flex gap-2">
                  <button class="tag-save-btn px-3 py-1.5 text-sm bg-action text-white rounded-button hover:bg-action-hover transition-colors">
                    Save
                  </button>
                  <button class="tag-cancel-btn px-3 py-1.5 text-sm bg-secondary text-white rounded-button hover:bg-secondary-hover transition-colors">
                    Cancel
                  </button>
                </div>
                <div class="tag-error hidden mt-2 p-2 bg-red-50 text-status-error rounded text-sm border border-status-error"></div>
              \`;

              wrapper.appendChild(display);
              wrapper.appendChild(edit);

              return wrapper;
            }

            attachEventListeners(wrapper, apiEndpoint) {
              const editBtn = wrapper.querySelector('.tag-edit-btn');
              const saveBtn = wrapper.querySelector('.tag-save-btn');
              const cancelBtn = wrapper.querySelector('.tag-cancel-btn');
              const addBtn = wrapper.querySelector('.tag-add-btn');
              const input = wrapper.querySelector('.tag-input');

              editBtn.addEventListener('click', () => this.startEditing(wrapper, apiEndpoint));
              saveBtn.addEventListener('click', () => this.saveTags(wrapper, apiEndpoint));
              cancelBtn.addEventListener('click', () => this.cancelEditing(wrapper));
              addBtn.addEventListener('click', () => this.addTag(wrapper));

              input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  this.addTag(wrapper);
                } else if (e.key === 'Escape') {
                  this.cancelEditing(wrapper);
                }
              });

              wrapper.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && e.ctrlKey) {
                  this.saveTags(wrapper, apiEndpoint);
                }
              });
            }

            startEditing(wrapper, apiEndpoint) {
              if (this.isEditing) return;

              this.isEditing = true;
              this.currentElement = wrapper;
              this.currentApiEndpoint = apiEndpoint;

              const display = wrapper.querySelector('.tag-display');
              const edit = wrapper.querySelector('.tag-edit');
              const input = wrapper.querySelector('.tag-input');

              const tagElements = display.querySelectorAll('.tag-list span:not(.text-text-muted)');
              this.originalTags = Array.from(tagElements).map(el => el.textContent.trim());
              this.currentTags = [...this.originalTags];

              display.classList.add('hidden');
              edit.classList.remove('hidden');

              this.renderEditTags(wrapper);
              input.focus();
            }

            renderEditTags(wrapper) {
              const tagListEdit = wrapper.querySelector('.tag-list-edit');

              if (this.currentTags.length === 0) {
                tagListEdit.innerHTML = '<span class="text-text-muted italic text-sm">No tags yet. Add one above.</span>';
                return;
              }

              tagListEdit.innerHTML = this.currentTags.map((tag, index) => \`
                <span class="inline-flex items-center gap-1 px-2 py-1 rounded bg-base-bg text-xs text-text-secondary border border-base-border">
                  \${escapeHtml(tag)}
                  <button class="tag-remove-btn text-text-muted hover:text-status-error transition-colors" data-index="\${index}">
                    ×
                  </button>
                </span>
              \`).join('');

              const removeBtns = tagListEdit.querySelectorAll('.tag-remove-btn');
              removeBtns.forEach(btn => {
                btn.addEventListener('click', (e) => {
                  e.preventDefault();
                  const index = parseInt(btn.dataset.index);
                  this.removeTag(wrapper, index);
                });
              });
            }

            addTag(wrapper) {
              const input = wrapper.querySelector('.tag-input');
              const errorDiv = wrapper.querySelector('.tag-error');
              const tag = input.value.trim();

              errorDiv.classList.add('hidden');

              if (!tag) {
                return;
              }

              if (tag.length > 50) {
                this.showError(wrapper, 'Tag is too long (max 50 characters)');
                return;
              }

              if (this.currentTags.includes(tag)) {
                this.showError(wrapper, 'Tag already exists');
                return;
              }

              this.currentTags.push(tag);
              input.value = '';

              this.renderEditTags(wrapper);
            }

            removeTag(wrapper, index) {
              this.currentTags.splice(index, 1);
              this.renderEditTags(wrapper);
            }

            cancelEditing(wrapper) {
              if (!this.isEditing) return;

              const display = wrapper.querySelector('.tag-display');
              const edit = wrapper.querySelector('.tag-edit');
              const input = wrapper.querySelector('.tag-input');
              const errorDiv = wrapper.querySelector('.tag-error');

              this.currentTags = [...this.originalTags];
              input.value = '';
              errorDiv.classList.add('hidden');

              edit.classList.add('hidden');
              display.classList.remove('hidden');

              this.resetEditingState();
            }

            async saveTags(wrapper, apiEndpoint) {
              if (!this.isEditing) return;

              const saveBtn = wrapper.querySelector('.tag-save-btn');
              const errorDiv = wrapper.querySelector('.tag-error');

              saveBtn.disabled = true;
              saveBtn.textContent = 'Saving...';
              errorDiv.classList.add('hidden');

              try {
                const response = await fetch(apiEndpoint, {
                  method: 'PUT',
                  headers: {
                    'Content-Type': 'application/json',
                  },
                  body: JSON.stringify({ tags: this.currentTags }),
                });

                if (!response.ok) {
                  const errorData = await response.json();
                  throw new Error(errorData.detail || \`Server error: \${response.status}\`);
                }

                const updatedMetadata = await response.json();

                this.updateDisplay(wrapper, updatedMetadata.tags || []);
                this.finishEditing(wrapper);
              } catch (error) {
                console.error('Error saving tags:', error);
                this.showError(wrapper, error.message || 'Failed to save tags');

                saveBtn.disabled = false;
                saveBtn.textContent = 'Save';
              }
            }

            updateDisplay(wrapper, tags) {
              const tagList = wrapper.querySelector('.tag-display .tag-list');

              if (tags.length > 0) {
                tagList.innerHTML = tags.map(tag =>
                  \`<span class="inline-flex items-center px-2 py-0.5 rounded-full bg-base-bg text-xs text-text-muted border border-base-border">\${escapeHtml(tag)}</span>\`
                ).join('');
              } else {
                tagList.innerHTML = '<span class="text-text-muted italic text-sm">No tags</span>';
              }
            }

            finishEditing(wrapper) {
              const display = wrapper.querySelector('.tag-display');
              const edit = wrapper.querySelector('.tag-edit');
              const saveBtn = wrapper.querySelector('.tag-save-btn');
              const input = wrapper.querySelector('.tag-input');

              edit.classList.add('hidden');
              display.classList.remove('hidden');

              saveBtn.disabled = false;
              saveBtn.textContent = 'Save';
              input.value = '';

              this.resetEditingState();
            }

            showError(wrapper, message) {
              const errorDiv = wrapper.querySelector('.tag-error');
              errorDiv.textContent = message;
              errorDiv.classList.remove('hidden');
            }

            resetEditingState() {
              this.isEditing = false;
              this.originalTags = [];
              this.currentTags = [];
              this.currentElement = null;
              this.currentApiEndpoint = null;
            }
          }

          window.TagEditor = TagEditor;

          // Initialize tag editor
          document.addEventListener('DOMContentLoaded', function() {
            const tagElement = document.getElementById('test-tags');
            if (tagElement) {
              const tagEditor = new TagEditor();
              const apiEndpoint = '/api/projects/test_project/metadata';
              tagEditor.init(tagElement, apiEndpoint, ['tag1', 'tag2']);
            }
          });
        </script>
      </body>
      </html>
    `);
  });

  test('displays initial tags', async ({ page }) => {
    const tagList = page.locator('.tag-list');
    await expect(tagList).toContainText('tag1');
    await expect(tagList).toContainText('tag2');

    const editBtn = page.locator('.tag-edit-btn');
    await expect(editBtn).toBeVisible();
    await expect(editBtn).toContainText('Edit');
  });

  test('enters edit mode when edit button is clicked', async ({ page }) => {
    const editBtn = page.locator('.tag-edit-btn');
    await editBtn.click();

    // Display should be hidden, edit should be visible
    const display = page.locator('.tag-display');
    const edit = page.locator('.tag-edit');

    await expect(display).toHaveClass(/hidden/);
    await expect(edit).not.toHaveClass(/hidden/);

    // Input should be focused
    const input = page.locator('.tag-input');
    await expect(input).toBeFocused();

    // Should show current tags in edit mode
    const tagListEdit = page.locator('.tag-list-edit');
    await expect(tagListEdit).toContainText('tag1');
    await expect(tagListEdit).toContainText('tag2');
  });

  test('adds tag when Add button is clicked', async ({ page }) => {
    const editBtn = page.locator('.tag-edit-btn');
    await editBtn.click();

    const input = page.locator('.tag-input');
    await input.fill('newtag');

    const addBtn = page.locator('.tag-add-btn');
    await addBtn.click();

    // New tag should appear in edit list
    const tagListEdit = page.locator('.tag-list-edit');
    await expect(tagListEdit).toContainText('newtag');

    // Input should be cleared
    await expect(input).toHaveValue('');
  });

  test('adds tag when Enter key is pressed', async ({ page }) => {
    const editBtn = page.locator('.tag-edit-btn');
    await editBtn.click();

    const input = page.locator('.tag-input');
    await input.fill('anothertag');
    await input.press('Enter');

    // New tag should appear
    const tagListEdit = page.locator('.tag-list-edit');
    await expect(tagListEdit).toContainText('anothertag');
  });

  test('prevents duplicate tags', async ({ page }) => {
    const editBtn = page.locator('.tag-edit-btn');
    await editBtn.click();

    const input = page.locator('.tag-input');
    await input.fill('tag1'); // Duplicate
    await input.press('Enter');

    // Should show error
    const errorDiv = page.locator('.tag-error');
    await expect(errorDiv).toContainText('Tag already exists');
  });

  test('prevents empty tags', async ({ page }) => {
    const editBtn = page.locator('.tag-edit-btn');
    await editBtn.click();

    const input = page.locator('.tag-input');
    await input.fill('   '); // Only spaces
    await input.press('Enter');

    // Should not add tag
    const tagListEdit = page.locator('.tag-list-edit');
    const content = await tagListEdit.textContent();
    expect(content).not.toContain('   ');
  });

  test('removes tag when remove button is clicked', async ({ page }) => {
    const editBtn = page.locator('.tag-edit-btn');
    await editBtn.click();

    // Click remove button for first tag
    const removeBtn = page.locator('.tag-remove-btn').first();
    await removeBtn.click();

    // Tag1 should be removed
    const tagListEdit = page.locator('.tag-list-edit');
    await expect(tagListEdit).not.toContainText('tag1');
    await expect(tagListEdit).toContainText('tag2'); // tag2 should remain
  });

  test('cancels editing when cancel button is clicked', async ({ page }) => {
    const editBtn = page.locator('.tag-edit-btn');
    await editBtn.click();

    // Add a new tag
    const input = page.locator('.tag-input');
    await input.fill('temptag');
    await input.press('Enter');

    // Click cancel
    const cancelBtn = page.locator('.tag-cancel-btn');
    await cancelBtn.click();

    // Should return to display mode
    const display = page.locator('.tag-display');
    const edit = page.locator('.tag-edit');

    await expect(display).not.toHaveClass(/hidden/);
    await expect(edit).toHaveClass(/hidden/);

    // Tags should remain unchanged
    const tagList = page.locator('.tag-list');
    await expect(tagList).toContainText('tag1');
    await expect(tagList).toContainText('tag2');
    await expect(tagList).not.toContainText('temptag');
  });

  test('cancels editing with Escape key', async ({ page }) => {
    const editBtn = page.locator('.tag-edit-btn');
    await editBtn.click();

    const input = page.locator('.tag-input');
    await input.fill('temptag');
    await input.press('Escape');

    // Should return to display mode
    const display = page.locator('.tag-display');
    await expect(display).not.toHaveClass(/hidden/);
  });

  test('saves tags when save button is clicked', async ({ page }) => {
    const editBtn = page.locator('.tag-edit-btn');
    await editBtn.click();

    // Add a new tag
    const input = page.locator('.tag-input');
    await input.fill('newtag');
    await input.press('Enter');

    // Click save
    const saveBtn = page.locator('.tag-save-btn');
    await saveBtn.click();

    // Should return to display mode
    const display = page.locator('.tag-display');
    await expect(display).not.toHaveClass(/hidden/);

    // New tag should be in display
    const tagList = page.locator('.tag-list');
    await expect(tagList).toContainText('newtag');
  });

  test('saves tags with Ctrl+Enter keyboard shortcut', async ({ page }) => {
    const editBtn = page.locator('.tag-edit-btn');
    await editBtn.click();

    const input = page.locator('.tag-input');
    await input.fill('quicktag');
    await input.press('Enter');

    // Press Ctrl+Enter to save
    await input.press('Control+Enter');

    // Should return to display mode
    const display = page.locator('.tag-display');
    await expect(display).not.toHaveClass(/hidden/);

    // Tag should be saved
    const tagList = page.locator('.tag-list');
    await expect(tagList).toContainText('quicktag');
  });

  test('shows loading state during save', async ({ page }) => {
    // Delay the API response
    await page.route('/api/projects/test_project/metadata', async (route) => {
      if (route.request().method() === 'PUT') {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            notes: '',
            tags: ['tag1', 'tag2', 'saved'],
            created_at: '2026-01-04T10:00:00',
            updated_at: '2026-01-04T10:00:00',
          }),
        });
      }
    });

    const editBtn = page.locator('.tag-edit-btn');
    await editBtn.click();

    const input = page.locator('.tag-input');
    await input.fill('savetag');
    await input.press('Enter');

    const saveBtn = page.locator('.tag-save-btn');
    await saveBtn.click();

    // Check loading state
    await expect(saveBtn).toContainText('Saving...');
    await expect(saveBtn).toBeDisabled();

    // Wait for save to complete
    await expect(saveBtn).toContainText('Save', { timeout: 2000 });
    await expect(saveBtn).not.toBeDisabled();
  });

  test('displays empty state when no tags', async ({ page }) => {
    // Re-initialize with no tags
    await page.evaluate(() => {
      const tagElement = document.getElementById('test-tags');
      if (tagElement) {
        const wrapper = tagElement.parentNode.querySelector('.tag-editor-wrapper');
        if (wrapper) {
          wrapper.remove();
        }
        const tagEditor = new window.TagEditor();
        const apiEndpoint = '/api/projects/test_project/metadata';
        tagEditor.init(tagElement, apiEndpoint, []);
      }
    });

    const tagList = page.locator('.tag-list');
    await expect(tagList).toContainText('No tags');
  });
});
