/**
 * Tag editor using @jcubic/tagger library
 */

import tagger from '@jcubic/tagger';
import { ICON_EDIT, escapeHtml } from './html-utils.js';

class TagEditor {
  constructor() {
    this.taggerInstance = null;
    this.isEditing = false;
  }

  /**
   * Initialize tag editor for an element
   * @param {HTMLElement} element - The tag display element
   * @param {string} apiEndpoint - API endpoint for updating tags
   * @param {Array<string>} currentTags - Current tag list
   */
  init(element, apiEndpoint, currentTags = []) {
    if (!element || !apiEndpoint) return;

    const { wrapper, editBtn, input, saveBtn, cancelBtn } = this.createTagWrapper(element, currentTags);
    element.parentNode.replaceChild(wrapper, element);

    // Set initial tags BEFORE initializing tagger
    // This is important because tagger needs to read the initial value on initialization
    input.value = currentTags.join(',');

    // Initialize tagger on input (after setting value)
    this.taggerInstance = tagger(input, {
      allow_duplicates: false,
      allow_spaces: false,
      wrap: true,
    });

    // Apply custom styles to tagger container for smaller font size and wider width
    const taggerContainer = input.parentElement;
    if (taggerContainer?.classList.contains('tagger')) {
      taggerContainer.style.fontSize = '0.75rem'; // 12px equivalent
      taggerContainer.style.minHeight = '1.5rem'; // Smaller minimum height for smaller font
      taggerContainer.style.width = '50em'; // Set explicit width for tagger container
      taggerContainer.style.maxWidth = '100%'; // Don't overflow parent
    }

    this.attachEventListeners(wrapper, editBtn, input, saveBtn, cancelBtn, apiEndpoint);
  }

  /**
   * Create tag wrapper with display and input elements
   */
  createTagWrapper(originalElement, tags) {
    const wrapper = document.createElement('div');
    wrapper.className = 'tag-editor-wrapper';

    // Display mode
    const display = document.createElement('div');
    display.className = 'tag-display flex items-center gap-2 flex-wrap';

    const tagsHtml =
      tags.length > 0
        ? tags
            .map(
              (tag) =>
                `<span class="inline-flex items-center px-2 py-0.5 rounded-full bg-base-bg text-xs text-text-muted border border-base-border">${escapeHtml(tag)}</span>`
            )
            .join('')
        : '<span class="text-text-muted italic text-sm">No tags</span>';

    display.innerHTML = `
      <div class="tag-list flex items-center gap-1.5 flex-wrap">${tagsHtml}</div>
    `;

    // Edit button
    const editBtn = document.createElement('button');
    editBtn.className = 'tag-edit-btn px-2 py-1 text-sm text-accent hover:text-accent-hover transition-colors';
    editBtn.innerHTML = `${ICON_EDIT} Edit`;
    display.appendChild(editBtn);

    // Edit mode (hidden input for tagger)
    const edit = document.createElement('div');
    edit.className = 'tag-edit hidden';
    // Set explicit width for edit area
    edit.style.width = '50em';
    edit.style.maxWidth = '100%'; // Don't overflow container

    const inputWrapper = document.createElement('div');
    inputWrapper.className = 'flex gap-2 items-center mb-2';

    const input = document.createElement('input');
    input.type = 'text';
    input.name = 'tags';
    input.className = 'tag-input flex-1';
    input.placeholder = 'Add tags...';
    // Use smaller font size with rem units
    input.style.fontSize = '0.75rem'; // 12px equivalent

    // Save button
    const saveBtn = document.createElement('button');
    saveBtn.className = 'tag-save-btn px-3 py-1.5 text-sm bg-accent text-white rounded-button hover:bg-accent-hover transition-colors';
    saveBtn.textContent = 'Save';

    // Cancel button
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'tag-cancel-btn px-3 py-1.5 text-sm bg-secondary text-white rounded-button hover:bg-secondary-hover transition-colors';
    cancelBtn.textContent = 'Cancel';

    inputWrapper.appendChild(input);
    inputWrapper.appendChild(cancelBtn);
    inputWrapper.appendChild(saveBtn);
    edit.appendChild(inputWrapper);

    // Error display
    const errorDiv = document.createElement('div');
    errorDiv.className = 'tag-error hidden mt-2 p-2 bg-red-50 text-status-error rounded text-sm border border-status-error';
    edit.appendChild(errorDiv);

    wrapper.appendChild(display);
    wrapper.appendChild(edit);

    return { wrapper, editBtn, input, saveBtn, cancelBtn };
  }

  /**
   * Attach event listeners
   */
  attachEventListeners(wrapper, editBtn, input, saveBtn, cancelBtn, apiEndpoint) {
    // Store the tags when entering edit mode for cancel restore
    let tagsBeforeEdit = [];

    // Prevent clicks from propagating to parent card
    wrapper.addEventListener('click', (e) => {
      e.stopPropagation();
    });

    // Edit button toggles edit mode
    editBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      // Save current tags before entering edit mode
      tagsBeforeEdit = input.value
        .split(',')
        .map((tag) => tag.trim())
        .filter((tag) => tag.length > 0);
      this.toggleEditMode(wrapper, input);
    });

    // Save button saves and closes edit mode
    saveBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        await this.saveTags(wrapper, input, apiEndpoint);
      } catch (error) {
        // Error is already logged in saveTags()
      }
      this.closeEditMode(wrapper, input);
    });

    // Cancel button discards changes and closes edit mode
    cancelBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      // Restore original tags and update display
      this.restoreTags(wrapper, input, tagsBeforeEdit);
      this.closeEditMode(wrapper, input);
    });

    // Close on Escape - cancel without saving
    wrapper.addEventListener(
      'keydown',
      (e) => {
        if (e.key === 'Escape' && this.isEditing) {
          e.preventDefault();
          e.stopPropagation();
          // Restore original tags and close (same as Cancel)
          this.restoreTags(wrapper, input, tagsBeforeEdit);
          this.closeEditMode(wrapper, input);
        }
      },
      true
    ); // true = capture phase
  }

  /**
   * Toggle edit mode
   */
  toggleEditMode(wrapper, input) {
    const display = wrapper.querySelector('.tag-display');
    const edit = wrapper.querySelector('.tag-edit');

    if (this.isEditing) {
      this.closeEditMode(wrapper, input);
    } else {
      display.classList.add('hidden');
      edit.classList.remove('hidden');
      this.isEditing = true;
      input.focus();
    }
  }

  /**
   * Close edit mode
   */
  closeEditMode(wrapper, input) {
    const display = wrapper.querySelector('.tag-display');
    const edit = wrapper.querySelector('.tag-edit');
    const errorDiv = wrapper.querySelector('.tag-error');

    errorDiv.classList.add('hidden');
    edit.classList.add('hidden');
    display.classList.remove('hidden');
    this.isEditing = false;
  }

  /**
   * Restore tags to a previous state (used by Cancel)
   */
  restoreTags(wrapper, input, tags) {
    // Update the input value
    input.value = tags.join(',');

    // Rebuild tagger UI by triggering a refresh
    // The tagger library reads from input.value, so we need to reinitialize the tags display
    const taggerContainer = input.parentElement;
    if (taggerContainer?.classList.contains('tagger')) {
      // Remove existing tag elements
      const existingTags = taggerContainer.querySelectorAll('.tagger-tag');
      for (const tag of existingTags) {
        tag.remove();
      }

      // Re-add tags from the restored value
      for (const tagText of tags) {
        const tagSpan = document.createElement('span');
        tagSpan.className = 'tagger-tag';
        tagSpan.innerHTML = `${escapeHtml(tagText)}<span class="tagger-close">×</span>`;
        // Insert before the input
        taggerContainer.insertBefore(tagSpan, input);
      }
    }

    // Update display
    this.updateDisplay(wrapper, tags);
  }

  /**
   * Save tags to server
   */
  async saveTags(wrapper, input, apiEndpoint) {
    const errorDiv = wrapper.querySelector('.tag-error');
    errorDiv.classList.add('hidden');

    // Get current tags from input
    const tags = input.value
      .split(',')
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0);

    try {
      const response = await fetch(apiEndpoint, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ tags }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const updatedMetadata = await response.json();

      // Update display with saved tags
      this.updateDisplay(wrapper, updatedMetadata.tags || []);
    } catch (error) {
      console.error('Error saving tags:', error);
      this.showError(wrapper, error.message || 'Failed to save tags');
    }
  }

  /**
   * Update the tag display with new content
   */
  updateDisplay(wrapper, tags) {
    const tagList = wrapper.querySelector('.tag-display .tag-list');

    if (tags.length > 0) {
      tagList.innerHTML = tags
        .map(
          (tag) =>
            `<span class="inline-flex items-center px-2 py-0.5 rounded-full bg-base-bg text-xs text-text-muted border border-base-border">${escapeHtml(tag)}</span>`
        )
        .join('');
    } else {
      tagList.innerHTML = '<span class="text-text-muted italic text-sm">No tags</span>';
    }
  }

  /**
   * Show error message
   */
  showError(wrapper, message) {
    const errorDiv = wrapper.querySelector('.tag-error');
    errorDiv.textContent = message;
    errorDiv.classList.remove('hidden');
  }
}

/**
 * Initialize tag editors for elements matching a selector
 * @param {string} selector - CSS selector for tag containers
 * @param {function} getApiEndpoint - Function that takes container and returns API endpoint (or null to skip)
 */
function initializeTagEditorsForElements(selector, getApiEndpoint) {
  const tagContainers = document.querySelectorAll(selector);
  for (const container of tagContainers) {
    const apiEndpoint = getApiEndpoint(container);
    if (!apiEndpoint) continue;

    const tagEditor = new TagEditor();

    // Get current tags (use :scope > span to get direct children only)
    const tagElements = container.querySelectorAll(':scope > span');
    const currentTags = Array.from(tagElements)
      .map((el) => el.textContent.trim())
      .filter((tag) => tag.length > 0);

    // Initialize tag editor
    tagEditor.init(container, apiEndpoint, currentTags);
  }
}

// Export for use in other scripts
export { TagEditor, initializeTagEditorsForElements };
window.TagEditor = TagEditor;
