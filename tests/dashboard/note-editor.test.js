/**
 * Unit tests for NoteEditor class
 */

import { beforeEach, describe, expect, test } from 'vitest';
import { NoteEditor } from '../../src/aspara/dashboard/static/js/note-editor.js';

describe('NoteEditor', () => {
  let container;

  beforeEach(() => {
    document.body.innerHTML = '';
    container = document.createElement('div');
    container.id = 'note-container';
    document.body.appendChild(container);
  });

  describe('multiple instances', () => {
    test('each instance should bind to its own edit button, not a global one', () => {
      // Create two note elements
      const note1 = document.createElement('div');
      note1.id = 'note-1';
      note1.textContent = 'Note 1';
      const note2 = document.createElement('div');
      note2.id = 'note-2';
      note2.textContent = 'Note 2';
      document.body.appendChild(note1);
      document.body.appendChild(note2);

      const editor1 = new NoteEditor();
      editor1.init(note1, '/api/note1', 'Note 1');

      const editor2 = new NoteEditor();
      editor2.init(note2, '/api/note2', 'Note 2');

      // Both should have their own edit buttons
      const editBtns = document.querySelectorAll('.note-edit-btn');
      expect(editBtns.length).toBe(2);

      // Clicking editor1's edit button should only affect editor1
      const wrapper1 = document.querySelectorAll('.note-editor-wrapper')[0];
      const wrapper2 = document.querySelectorAll('.note-editor-wrapper')[1];

      const editBtn1 = wrapper1.querySelector('.note-edit-btn');
      editBtn1.click();

      // editor1 should be editing, editor2 should not
      expect(editor1.isEditing).toBe(true);
      expect(editor2.isEditing).toBe(false);

      // Clean up
      editor1.destroy();
      editor2.destroy();
    });

    test('edit button in external container should still work', () => {
      // Create external button container
      const btnContainer = document.createElement('div');
      btnContainer.id = 'edit-btn-container';
      document.body.appendChild(btnContainer);

      const note = document.createElement('div');
      note.id = 'note-ext';
      document.body.appendChild(note);

      const editor = new NoteEditor();
      editor.init(note, '/api/note', 'Test note', 'edit-btn-container');

      // Edit button should be in the external container
      const editBtn = btnContainer.querySelector('.note-edit-btn');
      expect(editBtn).toBeTruthy();

      // Clicking it should start editing
      editBtn.click();
      expect(editor.isEditing).toBe(true);

      editor.destroy();
    });
  });

  describe('destroy', () => {
    test('should remove event listeners so edit button no longer works', () => {
      const note = document.createElement('div');
      note.id = 'note-destroy';
      document.body.appendChild(note);

      const editor = new NoteEditor();
      editor.init(note, '/api/note', 'Test');

      const wrapper = document.querySelector('.note-editor-wrapper');
      const editBtn = wrapper.querySelector('.note-edit-btn');

      // Edit button works before destroy
      editBtn.click();
      expect(editor.isEditing).toBe(true);

      // Cancel to reset
      const cancelBtn = wrapper.querySelector('.note-cancel-btn');
      cancelBtn.click();
      expect(editor.isEditing).toBe(false);

      // Destroy and verify edit button no longer works
      editor.destroy();
      editBtn.click();
      expect(editor.isEditing).toBe(false);
    });

    test('should be safe to call multiple times', () => {
      const note = document.createElement('div');
      document.body.appendChild(note);

      const editor = new NoteEditor();
      editor.init(note, '/api/note', 'Test');

      expect(() => {
        editor.destroy();
        editor.destroy();
      }).not.toThrow();
    });

    test('should be safe to call without init', () => {
      const editor = new NoteEditor();
      expect(() => {
        editor.destroy();
      }).not.toThrow();
    });
  });
});
