/**
 * Inline note editor functionality
 * GitHub Issue-style inline editing for project/run notes
 */

import {
  EMPTY_NOTE_PLACEHOLDER,
  createSaveNoteRequestBody,
  extractNoteFromResponse,
  extractNoteText,
  formatNoteForDisplay,
  getEditButtonHTML,
  isNoteEmpty,
} from './note-editor-utils.js';
import { guardReadOnly } from './read-only-guard.js';

class NoteEditor {
  constructor() {
    this.isEditing = false;
    this.originalValue = '';
    this.currentElement = null;
    this.currentApiEndpoint = null;
  }

  /**
   * Initialize note editor for an element
   * @param {HTMLElement} element - The note display element
   * @param {string} apiEndpoint - API endpoint for updating note
   * @param {string} currentNote - Current note content
   * @param {string} editButtonContainerId - ID of the container for the edit button
   */
  init(element, apiEndpoint, currentNote = '', editButtonContainerId = null) {
    if (!element || !apiEndpoint) return;

    const wrapper = this.createNoteWrapper(element, currentNote, editButtonContainerId);
    element.parentNode.replaceChild(wrapper, element);

    this.attachEventListeners(wrapper, apiEndpoint);
  }

  /**
   * Create note wrapper with display and edit elements
   */
  createNoteWrapper(originalElement, note, editButtonContainerId) {
    const wrapper = document.createElement('div');
    wrapper.className = 'note-editor-wrapper';

    const display = document.createElement('div');
    display.className = 'note-display';
    display.innerHTML = `<div class="note-content">${formatNoteForDisplay(note)}</div>`;

    // Create edit button
    const editBtn = document.createElement('button');
    editBtn.className = 'note-edit-btn py-1 text-sm text-accent hover:text-accent-hover transition-colors';
    editBtn.innerHTML = getEditButtonHTML();

    // Place edit button in specified container or in display
    if (editButtonContainerId) {
      const buttonContainer = document.getElementById(editButtonContainerId);
      if (buttonContainer) {
        buttonContainer.appendChild(editBtn);
      }
    } else {
      display.appendChild(editBtn);
    }

    // Edit element (hidden by default)
    const edit = document.createElement('div');
    edit.className = 'note-edit hidden';
    edit.innerHTML = `
            <textarea class="note-textarea w-full p-2 border border-base-border rounded focus:outline-none focus:ring-2 focus:ring-accent resize-none"
                      rows="3"
                      placeholder="Enter note..."
                      maxlength="1000"></textarea>
            <div class="note-actions mt-2 flex gap-2">
                <button class="note-cancel-btn px-3 py-1.5 text-sm bg-secondary text-white rounded-button hover:bg-secondary-hover transition-colors">
                    Cancel
                </button>
                <button class="note-save-btn px-3 py-1.5 text-sm bg-action text-white rounded-button hover:bg-action-hover transition-colors">
                    Save
                </button>
            </div>
            <div class="note-error hidden mt-2 p-2 bg-red-50 text-status-error rounded text-sm border border-status-error"></div>
        `;

    wrapper.appendChild(display);
    wrapper.appendChild(edit);

    return wrapper;
  }

  /**
   * Attach event listeners to note wrapper
   */
  attachEventListeners(wrapper, apiEndpoint) {
    // Edit button might be outside wrapper, so search globally
    const editBtn = document.querySelector('.note-edit-btn');
    const saveBtn = wrapper.querySelector('.note-save-btn');
    const cancelBtn = wrapper.querySelector('.note-cancel-btn');
    const textarea = wrapper.querySelector('.note-textarea');
    const noteContent = wrapper.querySelector('.note-content');

    if (editBtn) {
      editBtn.addEventListener('click', () => this.startEditing(wrapper, apiEndpoint));
    }

    // Click on placeholder text enters edit mode
    if (noteContent) {
      noteContent.addEventListener('click', () => {
        if (isNoteEmpty(noteContent.textContent)) {
          this.startEditing(wrapper, apiEndpoint);
        }
      });
    }

    saveBtn.addEventListener('click', () => this.saveNote(wrapper, apiEndpoint));
    cancelBtn.addEventListener('click', () => this.cancelEditing(wrapper));

    // Save on Ctrl+Enter, Cancel on Escape
    textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && e.ctrlKey) {
        this.saveNote(wrapper, apiEndpoint);
      } else if (e.key === 'Escape') {
        this.cancelEditing(wrapper);
      }
    });
  }

  /**
   * Start editing mode
   */
  startEditing(wrapper, apiEndpoint) {
    if (guardReadOnly()) return;
    if (this.isEditing) return; // Prevent multiple edits

    this.isEditing = true;
    this.currentElement = wrapper;
    this.currentApiEndpoint = apiEndpoint;

    const display = wrapper.querySelector('.note-display');
    const edit = wrapper.querySelector('.note-edit');
    const textarea = wrapper.querySelector('.note-textarea');
    const noteContent = wrapper.querySelector('.note-content');

    // Get current note text (strip HTML and handle empty state)
    const currentText = extractNoteText(noteContent.textContent);
    this.originalValue = currentText;

    display.classList.add('hidden');
    edit.classList.remove('hidden');
    textarea.value = currentText;
    textarea.focus();
  }

  /**
   * Cancel editing and restore original state
   */
  cancelEditing(wrapper) {
    if (!this.isEditing) return;

    const display = wrapper.querySelector('.note-display');
    const edit = wrapper.querySelector('.note-edit');
    const textarea = wrapper.querySelector('.note-textarea');
    const errorDiv = wrapper.querySelector('.note-error');

    // Reset textarea to original content and hide any error message
    textarea.value = this.originalValue;
    errorDiv.classList.add('hidden');

    edit.classList.add('hidden');
    display.classList.remove('hidden');

    this.resetEditingState();
  }

  /**
   * Save note to server
   */
  async saveNote(wrapper, apiEndpoint) {
    if (!this.isEditing) return;

    const textarea = wrapper.querySelector('.note-textarea');
    const saveBtn = wrapper.querySelector('.note-save-btn');
    const errorDiv = wrapper.querySelector('.note-error');
    const newNote = textarea.value.trim();

    // Show loading state
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    errorDiv.classList.add('hidden');

    try {
      const response = await fetch(apiEndpoint, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: createSaveNoteRequestBody(newNote),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const updatedMetadata = await response.json();

      this.updateDisplay(wrapper, extractNoteFromResponse(updatedMetadata));
      this.finishEditing(wrapper);
    } catch (error) {
      console.error('Error saving note:', error);
      this.showError(wrapper, error.message || 'Failed to save note');

      // Reset save button
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save';
    }
  }

  /**
   * Update the note display with new content
   */
  updateDisplay(wrapper, note) {
    const noteContent = wrapper.querySelector('.note-content');
    noteContent.innerHTML = formatNoteForDisplay(note);
  }

  /**
   * Finish editing and return to display mode
   */
  finishEditing(wrapper) {
    const display = wrapper.querySelector('.note-display');
    const edit = wrapper.querySelector('.note-edit');
    const saveBtn = wrapper.querySelector('.note-save-btn');

    edit.classList.add('hidden');
    display.classList.remove('hidden');

    // Re-enable save button with original text
    saveBtn.disabled = false;
    saveBtn.textContent = 'Save';

    this.resetEditingState();
  }

  /**
   * Show error message
   */
  showError(wrapper, message) {
    const errorDiv = wrapper.querySelector('.note-error');
    errorDiv.textContent = message;
    errorDiv.classList.remove('hidden');
  }

  /**
   * Reset editing state
   */
  resetEditingState() {
    this.isEditing = false;
    this.originalValue = '';
    this.currentElement = null;
    this.currentApiEndpoint = null;
  }
}

/**
 * Initialize note editor from DOM element with data attributes
 * Expected data attributes on the element:
 * - data-api-endpoint: API endpoint for saving/loading notes
 * - data-edit-btn-id: ID of the edit button container
 *
 * @param {string} elementId - ID of the note element
 */
async function initNoteEditorFromDOM(elementId) {
  const noteElement = document.getElementById(elementId);
  if (!noteElement) return;

  const apiEndpoint = noteElement.dataset.apiEndpoint;
  const editBtnId = noteElement.dataset.editBtnId;

  if (!apiEndpoint) {
    console.error(`Note editor: missing data-api-endpoint on #${elementId}`);
    return;
  }

  const noteEditor = new NoteEditor();

  try {
    const response = await fetch(apiEndpoint);
    const metadata = await response.json();
    noteEditor.init(noteElement, apiEndpoint, metadata.notes || '', editBtnId);
  } catch (error) {
    console.error(`Error loading note for #${elementId}:`, error);
    noteEditor.init(noteElement, apiEndpoint, '', editBtnId);
  }
}

// Export for use in other scripts
export { NoteEditor, initNoteEditorFromDOM };
window.NoteEditor = NoteEditor;
window.initNoteEditorFromDOM = initNoteEditorFromDOM;
