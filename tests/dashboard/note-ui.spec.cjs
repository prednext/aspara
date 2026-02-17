/**
 * Playwright tests for note editor UI functionality
 */

const { test, expect } = require('@playwright/test');

test.describe('Note Editor UI', () => {
  test.beforeEach(async ({ page }) => {
    // Mock API responses
    await page.route('/api/projects/test_project/runs/test_run/metadata', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            notes: '',
            tags: [],
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
            notes: postData.note || '',
            tags: postData.tags || [],
            created_at: '2025-06-16T10:00:00',
            updated_at: '2025-06-16T10:00:00',
          }),
        });
      }
    });

    // Set up a test page with note editor
    await page.setContent(`
      <!DOCTYPE html>
      <html>
      <head>
        <script src="https://cdn.tailwindcss.com"></script>
      </head>
      <body>
        <div id="test-note" class="text-sm text-neutral-600"></div>
        <script>
          class NoteEditor {
            constructor() {
              this.isEditing = false;
              this.originalValue = '';
              this.currentElement = null;
              this.currentApiEndpoint = null;
            }

            init(element, apiEndpoint, currentNote = '') {
              if (!element || !apiEndpoint) return;

              const wrapper = this.createNoteWrapper(element, currentNote);
              element.parentNode.replaceChild(wrapper, element);

              this.attachEventListeners(wrapper, apiEndpoint);
            }

            createNoteWrapper(originalElement, note) {
              const wrapper = document.createElement('div');
              wrapper.className = 'note-editor-wrapper';

              const display = document.createElement('div');
              display.className = 'note-display';
              display.innerHTML = \`
                <div class="note-content">\${note || '<span class="text-gray-500 italic">ノートを追加...</span>'}</div>
                <button class="note-edit-btn ml-2 px-2 py-1 text-sm text-blue-500 hover:text-blue-700 transition-colors">
                  編集
                </button>
              \`;

              const edit = document.createElement('div');
              edit.className = 'note-edit hidden';
              edit.innerHTML = \`
                <textarea class="note-textarea w-full p-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                          rows="3"
                          placeholder="ノートを入力してください..."
                          maxlength="1000"></textarea>
                <div class="note-actions mt-2 flex gap-2">
                  <button class="note-save-btn px-3 py-1 text-sm bg-green-500 text-white rounded hover:bg-green-600 transition-colors">
                    保存
                  </button>
                  <button class="note-cancel-btn px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600 transition-colors">
                    キャンセル
                  </button>
                </div>
                <div class="note-error hidden mt-2 p-2 bg-red-100 text-red-700 rounded text-sm"></div>
              \`;

              wrapper.appendChild(display);
              wrapper.appendChild(edit);

              return wrapper;
            }

            attachEventListeners(wrapper, apiEndpoint) {
              const editBtn = wrapper.querySelector('.note-edit-btn');
              const saveBtn = wrapper.querySelector('.note-save-btn');
              const cancelBtn = wrapper.querySelector('.note-cancel-btn');
              const textarea = wrapper.querySelector('.note-textarea');

              editBtn.addEventListener('click', () => this.startEditing(wrapper, apiEndpoint));
              saveBtn.addEventListener('click', () => this.saveNote(wrapper, apiEndpoint));
              cancelBtn.addEventListener('click', () => this.cancelEditing(wrapper));

              textarea.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && e.ctrlKey) {
                  this.saveNote(wrapper, apiEndpoint);
                } else if (e.key === 'Escape') {
                  this.cancelEditing(wrapper);
                }
              });
            }

            startEditing(wrapper, apiEndpoint) {
              if (this.isEditing) return;

              this.isEditing = true;
              this.currentElement = wrapper;
              this.currentApiEndpoint = apiEndpoint;

              const display = wrapper.querySelector('.note-display');
              const edit = wrapper.querySelector('.note-edit');
              const textarea = wrapper.querySelector('.note-textarea');
              const noteContent = wrapper.querySelector('.note-content');

              const currentText = noteContent.textContent === 'ノートを追加...' ? '' : noteContent.textContent;
              this.originalValue = currentText;

              display.classList.add('hidden');
              edit.classList.remove('hidden');
              textarea.value = currentText;
              textarea.focus();
            }

            cancelEditing(wrapper) {
              if (!this.isEditing) return;

              const display = wrapper.querySelector('.note-display');
              const edit = wrapper.querySelector('.note-edit');
              const textarea = wrapper.querySelector('.note-textarea');
              const errorDiv = wrapper.querySelector('.note-error');

              textarea.value = this.originalValue;
              errorDiv.classList.add('hidden');

              edit.classList.add('hidden');
              display.classList.remove('hidden');

              this.resetEditingState();
            }

            async saveNote(wrapper, apiEndpoint) {
              if (!this.isEditing) return;

              const textarea = wrapper.querySelector('.note-textarea');
              const saveBtn = wrapper.querySelector('.note-save-btn');
              const errorDiv = wrapper.querySelector('.note-error');
              const newNote = textarea.value.trim();

              saveBtn.disabled = true;
              saveBtn.textContent = '保存中...';
              errorDiv.classList.add('hidden');

              try {
                const response = await fetch(apiEndpoint, {
                  method: 'PUT',
                  headers: {
                    'Content-Type': 'application/json',
                  },
                  body: JSON.stringify({ notes: newNote })
                });

                if (!response.ok) {
                  const errorData = await response.json();
                  throw new Error(errorData.detail || \`サーバーエラー: \${response.status}\`);
                }

                const updatedMetadata = await response.json();

                this.updateDisplay(wrapper, updatedMetadata.note || '');
                this.finishEditing(wrapper);

              } catch (error) {
                console.error('Error saving notes:', error);
                this.showError(wrapper, error.message || 'ノートの保存に失敗しました');

                saveBtn.disabled = false;
                saveBtn.textContent = '保存';
              }
            }

            updateDisplay(wrapper, note) {
              const noteContent = wrapper.querySelector('.note-content');

              if (note) {
                const escapedNote = note.replace(/&/g, '&amp;')
                                       .replace(/</g, '&lt;')
                                       .replace(/>/g, '&gt;')
                                       .replace(/\\n/g, '<br>');
                noteContent.innerHTML = escapedNote;
              } else {
                noteContent.innerHTML = '<span class="text-gray-500 italic">ノートを追加...</span>';
              }
            }

            finishEditing(wrapper) {
              const display = wrapper.querySelector('.note-display');
              const edit = wrapper.querySelector('.note-edit');
              const saveBtn = wrapper.querySelector('.note-save-btn');

              edit.classList.add('hidden');
              display.classList.remove('hidden');

              saveBtn.disabled = false;
              saveBtn.textContent = '保存';

              this.resetEditingState();
            }

            showError(wrapper, message) {
              const errorDiv = wrapper.querySelector('.note-error');
              errorDiv.textContent = message;
              errorDiv.classList.remove('hidden');
            }

            resetEditingState() {
              this.isEditing = false;
              this.originalValue = '';
              this.currentElement = null;
              this.currentApiEndpoint = null;
            }
          }

          window.NoteEditor = NoteEditor;

          // Initialize note editor
          document.addEventListener('DOMContentLoaded', function() {
            const noteElement = document.getElementById('test-note');
            if (noteElement) {
              const noteEditor = new NoteEditor();
              const apiEndpoint = '/api/projects/test_project/runs/test_run/metadata';
              noteEditor.init(noteElement, apiEndpoint, '');
            }
          });
        </script>
      </body>
      </html>
    `);
  });

  test('displays initial empty note state', async ({ page }) => {
    const noteContent = page.locator('.note-content');
    await expect(noteContent).toContainText('ノートを追加...');

    const editBtn = page.locator('.note-edit-btn');
    await expect(editBtn).toBeVisible();
    await expect(editBtn).toContainText('編集');
  });

  test('enters edit mode when edit button is clicked', async ({ page }) => {
    const editBtn = page.locator('.note-edit-btn');
    await editBtn.click();

    // Display should be hidden, edit should be visible
    const display = page.locator('.note-display');
    const edit = page.locator('.note-edit');

    await expect(display).toHaveClass(/hidden/);
    await expect(edit).not.toHaveClass(/hidden/);

    // Textarea should be focused
    const textarea = page.locator('.note-textarea');
    await expect(textarea).toBeFocused();
  });

  test('cancels editing when cancel button is clicked', async ({ page }) => {
    const editBtn = page.locator('.note-edit-btn');
    await editBtn.click();

    // Enter some text
    const textarea = page.locator('.note-textarea');
    await textarea.fill('Test note content');

    // Click cancel
    const cancelBtn = page.locator('.note-cancel-btn');
    await cancelBtn.click();

    // Should return to display mode
    const display = page.locator('.note-display');
    const edit = page.locator('.note-edit');

    await expect(display).not.toHaveClass(/hidden/);
    await expect(edit).toHaveClass(/hidden/);

    // Content should remain unchanged
    const noteContent = page.locator('.note-content');
    await expect(noteContent).toContainText('ノートを追加...');
  });

  test('saves note when save button is clicked', async ({ page }) => {
    const editBtn = page.locator('.note-edit-btn');
    await editBtn.click();

    // Enter note content
    const textarea = page.locator('.note-textarea');
    const noteText = 'Test note content for saving';
    await textarea.fill(noteText);

    // Click save
    const saveBtn = page.locator('.note-save-btn');
    await saveBtn.click();

    // Should return to display mode
    const display = page.locator('.note-display');
    const edit = page.locator('.note-edit');

    await expect(display).not.toHaveClass(/hidden/);
    await expect(edit).toHaveClass(/hidden/);

    // Content should be updated
    const noteContent = page.locator('.note-content');
    await expect(noteContent).toContainText(noteText);
  });

  test('saves note with Ctrl+Enter keyboard shortcut', async ({ page }) => {
    const editBtn = page.locator('.note-edit-btn');
    await editBtn.click();

    // Enter note content
    const textarea = page.locator('.note-textarea');
    const noteText = 'Note saved with keyboard shortcut';
    await textarea.fill(noteText);

    // Press Ctrl+Enter
    await textarea.press('Control+Enter');

    // Should return to display mode
    const display = page.locator('.note-display');
    await expect(display).not.toHaveClass(/hidden/);

    // Content should be updated
    const noteContent = page.locator('.note-content');
    await expect(noteContent).toContainText(noteText);
  });

  test('cancels editing with Escape key', async ({ page }) => {
    const editBtn = page.locator('.note-edit-btn');
    await editBtn.click();

    // Enter some text
    const textarea = page.locator('.note-textarea');
    await textarea.fill('Text that should be cancelled');

    // Press Escape
    await textarea.press('Escape');

    // Should return to display mode
    const display = page.locator('.note-display');
    const edit = page.locator('.note-edit');

    await expect(display).not.toHaveClass(/hidden/);
    await expect(edit).toHaveClass(/hidden/);

    // Content should remain unchanged
    const noteContent = page.locator('.note-content');
    await expect(noteContent).toContainText('ノートを追加...');
  });

  test('handles multi-line note content', async ({ page }) => {
    const editBtn = page.locator('.note-edit-btn');
    await editBtn.click();

    // Enter multi-line content
    const textarea = page.locator('.note-textarea');
    const multiLineNote = 'Line 1\nLine 2\nLine 3';
    await textarea.fill(multiLineNote);

    // Save
    const saveBtn = page.locator('.note-save-btn');
    await saveBtn.click();

    // Content should contain <br> tags for line breaks
    const noteContent = page.locator('.note-content');
    const innerHTML = await noteContent.innerHTML();
    expect(innerHTML).toContain('Line 1<br>Line 2<br>Line 3');
  });

  test('prevents multiple simultaneous edits', async ({ page }) => {
    const editBtn = page.locator('.note-edit-btn');

    // Click edit button twice quickly
    await editBtn.click();
    await editBtn.click();

    // Should only be in edit mode once
    const editSections = page.locator('.note-edit:not(.hidden)');
    await expect(editSections).toHaveCount(1);
  });

  test('shows loading state during save', async ({ page }) => {
    // Delay the API response to test loading state
    await page.route('/api/projects/test_project/runs/test_run/metadata', async (route) => {
      if (route.request().method() === 'PUT') {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            notes: 'saved',
            tags: [],
            created_at: '2025-06-16T10:00:00',
            updated_at: '2025-06-16T10:00:00',
          }),
        });
      }
    });

    const editBtn = page.locator('.note-edit-btn');
    await editBtn.click();

    const textarea = page.locator('.note-textarea');
    await textarea.fill('Test note');

    const saveBtn = page.locator('.note-save-btn');
    await saveBtn.click();

    // Check loading state
    await expect(saveBtn).toContainText('保存中...');
    await expect(saveBtn).toBeDisabled();

    // Wait for save to complete
    await expect(saveBtn).toContainText('保存');
    await expect(saveBtn).not.toBeDisabled();
  });
});
