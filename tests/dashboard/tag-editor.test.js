/**
 * Unit tests for TagEditor
 */

import { beforeEach, describe, expect, test, vi } from 'vitest';
import { TagEditor } from '../../src/aspara/dashboard/static/js/tag-editor.js';

// Mock tagger library
vi.mock('@jcubic/tagger', () => ({
  default: vi.fn(() => ({
    // Mock tagger instance
  })),
}));

describe('TagEditor', () => {
  let container;
  let tagEditor;

  beforeEach(() => {
    // Clean up DOM before each test
    document.body.innerHTML = '';

    // Create a container element
    container = document.createElement('div');
    container.id = 'test-tags';
    container.innerHTML = '<span>tag1</span><span>tag2</span>';
    document.body.appendChild(container);

    tagEditor = new TagEditor();
  });

  describe('Initialization', () => {
    test('should display existing tags on init', () => {
      const currentTags = ['test-tag-1', 'test-tag-2', 'test-tag-3'];
      tagEditor.init(container, '/api/test/metadata', currentTags);

      const wrapper = document.querySelector('.tag-editor-wrapper');
      expect(wrapper).toBeTruthy();

      const display = wrapper.querySelector('.tag-display');
      expect(display.textContent).toContain('test-tag-1');
      expect(display.textContent).toContain('test-tag-2');
      expect(display.textContent).toContain('test-tag-3');
      expect(display.textContent).not.toContain('No tags');
    });

    test('should display "No tags" when no tags exist', () => {
      tagEditor.init(container, '/api/test/metadata', []);

      const wrapper = document.querySelector('.tag-editor-wrapper');
      const display = wrapper.querySelector('.tag-display');
      expect(display.textContent).toContain('No tags');
    });

    test('should create Edit button', () => {
      tagEditor.init(container, '/api/test/metadata', ['tag1']);

      const editBtn = document.querySelector('.tag-edit-btn');
      expect(editBtn).toBeTruthy();
      expect(editBtn.textContent.trim()).toContain('Edit');
    });

    test('should create hidden edit mode initially', () => {
      tagEditor.init(container, '/api/test/metadata', ['tag1']);

      const edit = document.querySelector('.tag-edit');
      expect(edit).toBeTruthy();
      expect(edit.classList.contains('hidden')).toBe(true);
    });
  });

  describe('Edit Mode Toggle', () => {
    beforeEach(() => {
      tagEditor.init(container, '/api/test/metadata', ['tag1', 'tag2']);
    });

    test('should open edit mode when Edit button is clicked', () => {
      const editBtn = document.querySelector('.tag-edit-btn');
      const display = document.querySelector('.tag-display');
      const edit = document.querySelector('.tag-edit');

      editBtn.click();

      expect(display.classList.contains('hidden')).toBe(true);
      expect(edit.classList.contains('hidden')).toBe(false);
      expect(tagEditor.isEditing).toBe(true);
    });

    test('should have Save and Cancel buttons in edit mode', () => {
      const saveBtn = document.querySelector('.tag-save-btn');
      const cancelBtn = document.querySelector('.tag-cancel-btn');
      expect(saveBtn).toBeTruthy();
      expect(cancelBtn).toBeTruthy();
      expect(saveBtn.textContent).toBe('Save');
      expect(cancelBtn.textContent).toBe('Cancel');
    });

    test('should close edit mode when Save button is clicked', async () => {
      const editBtn = document.querySelector('.tag-edit-btn');
      editBtn.click();

      const saveBtn = document.querySelector('.tag-save-btn');
      const display = document.querySelector('.tag-display');
      const edit = document.querySelector('.tag-edit');

      saveBtn.click();

      // Wait for async operations to complete
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(display.classList.contains('hidden')).toBe(false);
      expect(edit.classList.contains('hidden')).toBe(true);
      expect(tagEditor.isEditing).toBe(false);
    });

    test('should close edit mode when Cancel button is clicked', async () => {
      const editBtn = document.querySelector('.tag-edit-btn');
      editBtn.click();

      const cancelBtn = document.querySelector('.tag-cancel-btn');
      const display = document.querySelector('.tag-display');
      const edit = document.querySelector('.tag-edit');

      cancelBtn.click();

      // Wait for async operations to complete
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(display.classList.contains('hidden')).toBe(false);
      expect(edit.classList.contains('hidden')).toBe(true);
      expect(tagEditor.isEditing).toBe(false);
    });

    test('should close edit mode when Escape key is pressed', async () => {
      const editBtn = document.querySelector('.tag-edit-btn');
      editBtn.click();

      const input = document.querySelector('.tag-input');
      const display = document.querySelector('.tag-display');
      const edit = document.querySelector('.tag-edit');

      // Simulate Escape key press
      const escapeEvent = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true });
      input.dispatchEvent(escapeEvent);

      // Wait for async operations to complete
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(display.classList.contains('hidden')).toBe(false);
      expect(edit.classList.contains('hidden')).toBe(true);
      expect(tagEditor.isEditing).toBe(false);
    });
  });

  describe('Tag Display Update', () => {
    beforeEach(() => {
      tagEditor.init(container, '/api/test/metadata', ['initial-tag']);
    });

    test('should update display with new tags', () => {
      const wrapper = document.querySelector('.tag-editor-wrapper');
      const newTags = ['new-tag-1', 'new-tag-2'];

      tagEditor.updateDisplay(wrapper, newTags);

      const display = wrapper.querySelector('.tag-display');
      expect(display.textContent).toContain('new-tag-1');
      expect(display.textContent).toContain('new-tag-2');
      expect(display.textContent).not.toContain('initial-tag');
      expect(display.textContent).not.toContain('No tags');
    });

    test('should show "No tags" when updated with empty array', () => {
      const wrapper = document.querySelector('.tag-editor-wrapper');

      tagEditor.updateDisplay(wrapper, []);

      const display = wrapper.querySelector('.tag-display');
      expect(display.textContent).toContain('No tags');
    });

    test('should preserve existing tags in display after save', () => {
      const wrapper = document.querySelector('.tag-editor-wrapper');
      const tags = ['tag-a', 'tag-b', 'tag-c'];

      tagEditor.updateDisplay(wrapper, tags);

      const display = wrapper.querySelector('.tag-display');
      expect(display.textContent).toContain('tag-a');
      expect(display.textContent).toContain('tag-b');
      expect(display.textContent).toContain('tag-c');
    });
  });

  describe('Edit Mode - Existing Tags', () => {
    test('BUG: existing tags should be visible in input when opening edit mode', () => {
      // Clean up first
      document.body.innerHTML = '';

      const container = document.createElement('div');
      container.id = 'test-tags';
      document.body.appendChild(container);

      const existingTags = ['tag-a', 'tag-b', 'tag-c'];
      const newTagEditor = new TagEditor();
      newTagEditor.init(container, '/api/test/metadata', existingTags);

      // Verify initial display shows tags
      const wrapper = document.querySelector('.tag-editor-wrapper');
      const display = wrapper.querySelector('.tag-display');
      expect(display.textContent).toContain('tag-a');
      expect(display.textContent).toContain('tag-b');
      expect(display.textContent).toContain('tag-c');

      // Open edit mode
      const editBtn = wrapper.querySelector('.tag-edit-btn');
      editBtn.click();

      // BUG: Input should contain existing tags in comma-separated format
      const input = wrapper.querySelector('.tag-input');
      expect(input.value).toBe('tag-a,tag-b,tag-c');
    });
  });

  describe('Error Handling', () => {
    beforeEach(() => {
      tagEditor.init(container, '/api/test/metadata', ['tag1']);
    });

    test('should show error message', () => {
      const wrapper = document.querySelector('.tag-editor-wrapper');
      const errorMessage = 'Test error message';

      tagEditor.showError(wrapper, errorMessage);

      const errorDiv = wrapper.querySelector('.tag-error');
      expect(errorDiv.textContent).toBe(errorMessage);
      expect(errorDiv.classList.contains('hidden')).toBe(false);
    });

    test('should hide error when closing edit mode', () => {
      const wrapper = document.querySelector('.tag-editor-wrapper');
      const input = wrapper.querySelector('.tag-input');

      // Show error first
      tagEditor.showError(wrapper, 'Error');

      // Close edit mode
      tagEditor.closeEditMode(wrapper, input);

      const errorDiv = wrapper.querySelector('.tag-error');
      expect(errorDiv.classList.contains('hidden')).toBe(true);
    });
  });

  describe('Real-world scenario: Server-rendered tags', () => {
    test('FIX: projects-list should extract tags with text-text-muted class correctly', () => {
      // Clean up first
      document.body.innerHTML = '';

      // Simulate ACTUAL HTML from projects_list.mustache template (line 48)
      const projectTagsContainer = document.createElement('div');
      projectTagsContainer.id = 'project-tags-default';
      projectTagsContainer.className = 'flex items-center gap-1.5 flex-wrap';
      projectTagsContainer.setAttribute('data-project-name', 'default');

      // This is EXACTLY how tags are rendered in projects_list.mustache
      projectTagsContainer.innerHTML = `
        <span class="inline-flex items-center px-2 py-0.5 rounded-full bg-base-bg text-xs text-text-muted border border-base-border">baseline</span>
        <span class="inline-flex items-center px-2 py-0.5 rounded-full bg-base-bg text-xs text-text-muted border border-base-border">experiment</span>
        <span class="inline-flex items-center px-2 py-0.5 rounded-full bg-base-bg text-xs text-text-muted border border-base-border">production</span>
      `;

      document.body.appendChild(projectTagsContainer);

      // Extract tags THE SAME WAY projects-list.js does AFTER FIX (using :scope > span)
      const tagElements = projectTagsContainer.querySelectorAll(':scope > span');
      const currentTags = Array.from(tagElements)
        .map((el) => el.textContent.trim())
        .filter((tag) => tag.length > 0);

      // FIX: Now it correctly extracts all tags!
      expect(currentTags).toEqual(['baseline', 'experiment', 'production']);

      // Initialize tag editor with the correctly extracted tags
      const newTagEditor = new TagEditor();
      newTagEditor.init(projectTagsContainer, '/api/projects/default/metadata', currentTags);

      // Verify tags are displayed correctly
      const wrapper = document.querySelector('.tag-editor-wrapper');
      const display = wrapper.querySelector('.tag-display');

      // All tags should be visible
      expect(display.textContent).toContain('baseline');
      expect(display.textContent).toContain('experiment');
      expect(display.textContent).toContain('production');
      expect(display.textContent).not.toContain('No tags');
    });

    test('should display existing tags from server-rendered HTML', () => {
      // Clean up first
      document.body.innerHTML = '';

      // Simulate actual HTML structure from runs_list.mustache template
      const runTagsContainer = document.createElement('div');
      runTagsContainer.id = 'run-tags-default-run1';
      runTagsContainer.className = 'flex flex-wrap gap-1.5 ml-6';
      runTagsContainer.setAttribute('data-project-name', 'default');
      runTagsContainer.setAttribute('data-run-name', 'run1');

      // Add server-rendered tags (same structure as template)
      runTagsContainer.innerHTML = `
        <span class="px-2 py-0.5 text-xs bg-base-bg text-text-secondary border border-base-border rounded">experiment</span>
        <span class="px-2 py-0.5 text-xs bg-base-bg text-text-secondary border border-base-border rounded">production</span>
        <span class="px-2 py-0.5 text-xs bg-base-bg text-text-secondary border border-base-border rounded">v1.0</span>
      `;

      document.body.appendChild(runTagsContainer);

      // Extract tags the same way runs-list.js does
      const tagElements = runTagsContainer.querySelectorAll('span:not(.text-text-muted)');
      const currentTags = Array.from(tagElements).map((el) => el.textContent.trim());

      // Verify we extracted tags correctly
      expect(currentTags).toEqual(['experiment', 'production', 'v1.0']);

      // Initialize tag editor with extracted tags
      const newTagEditor = new TagEditor();
      newTagEditor.init(runTagsContainer, '/api/projects/default/runs/run1/metadata', currentTags);

      // Verify the tag editor wrapper was created
      const wrapper = document.querySelector('.tag-editor-wrapper');
      expect(wrapper).toBeTruthy();

      // Verify existing tags are displayed
      const display = wrapper.querySelector('.tag-display');
      expect(display.textContent).toContain('experiment');
      expect(display.textContent).toContain('production');
      expect(display.textContent).toContain('v1.0');
      expect(display.textContent).not.toContain('No tags');

      // Verify all three tags are shown
      const displayedTags = display.querySelectorAll('.tag-list span.inline-flex');
      expect(displayedTags.length).toBe(3);
    });

    test('should handle empty tags from server', () => {
      // Clean up first
      document.body.innerHTML = '';

      // Simulate HTML with no tags
      const runTagsContainer = document.createElement('div');
      runTagsContainer.id = 'run-tags-default-run2';
      runTagsContainer.className = 'flex flex-wrap gap-1.5 ml-6';
      runTagsContainer.setAttribute('data-project-name', 'default');
      runTagsContainer.setAttribute('data-run-name', 'run2');
      // No tags in HTML

      document.body.appendChild(runTagsContainer);

      // Extract tags
      const tagElements = runTagsContainer.querySelectorAll('span:not(.text-text-muted)');
      const currentTags = Array.from(tagElements).map((el) => el.textContent.trim());

      // Verify no tags extracted
      expect(currentTags).toEqual([]);

      // Initialize tag editor
      const newTagEditor = new TagEditor();
      newTagEditor.init(runTagsContainer, '/api/projects/default/runs/run2/metadata', currentTags);

      // Verify "No tags" is shown
      const wrapper = document.querySelector('.tag-editor-wrapper');
      const display = wrapper.querySelector('.tag-display');
      expect(display.textContent).toContain('No tags');
    });

    test('existing tags should remain after opening and clicking Cancel', () => {
      // Clean up first
      document.body.innerHTML = '';

      // Simulate server-rendered HTML with existing tags
      const runTagsContainer = document.createElement('div');
      runTagsContainer.id = 'run-tags-proj-run';
      runTagsContainer.className = 'flex flex-wrap gap-1.5 ml-6';
      runTagsContainer.setAttribute('data-project-name', 'proj');
      runTagsContainer.setAttribute('data-run-name', 'run');
      runTagsContainer.innerHTML = `
        <span class="px-2 py-0.5 text-xs bg-base-bg text-text-secondary border border-base-border rounded">existing-tag-1</span>
        <span class="px-2 py-0.5 text-xs bg-base-bg text-text-secondary border border-base-border rounded">existing-tag-2</span>
      `;

      document.body.appendChild(runTagsContainer);

      // Extract tags and initialize (same as runs-list.js does)
      const tagElements = runTagsContainer.querySelectorAll('span:not(.text-text-muted)');
      const currentTags = Array.from(tagElements).map((el) => el.textContent.trim());
      expect(currentTags).toEqual(['existing-tag-1', 'existing-tag-2']);

      const newTagEditor = new TagEditor();
      newTagEditor.init(runTagsContainer, '/api/test/metadata', currentTags);

      // Verify tags are displayed initially
      const wrapper = document.querySelector('.tag-editor-wrapper');
      let display = wrapper.querySelector('.tag-display');
      expect(display.textContent).toContain('existing-tag-1');
      expect(display.textContent).toContain('existing-tag-2');
      expect(display.textContent).not.toContain('No tags');

      // Open edit mode
      const editBtn = wrapper.querySelector('.tag-edit-btn');
      editBtn.click();

      // Verify edit mode is open
      const edit = wrapper.querySelector('.tag-edit');
      expect(edit.classList.contains('hidden')).toBe(false);

      // Cancel edit mode WITHOUT making changes
      const cancelBtn = wrapper.querySelector('.tag-cancel-btn');
      cancelBtn.click();

      // After cancel, existing tags should still be visible!
      display = wrapper.querySelector('.tag-display');
      expect(display.textContent).toContain('existing-tag-1');
      expect(display.textContent).toContain('existing-tag-2');
      expect(display.textContent).not.toContain('No tags');
    });

    test('BUG REPRODUCTION: tags disappear after TagEditor replaces the container', () => {
      // Clean up first
      document.body.innerHTML = '';

      // Create a run card with tags (simulating full server-rendered structure)
      const runCard = document.createElement('div');
      runCard.className = 'run-card';
      runCard.innerHTML = `
        <div class="flex items-center justify-between mb-2">
          <div class="font-semibold">test-run</div>
        </div>
        <div id="run-tags-myproject-testrun" class="flex flex-wrap gap-1.5 ml-6" data-project-name="myproject" data-run-name="testrun">
          <span class="px-2 py-0.5 text-xs bg-base-bg text-text-secondary border border-base-border rounded">tag1</span>
          <span class="px-2 py-0.5 text-xs bg-base-bg text-text-secondary border border-base-border rounded">tag2</span>
        </div>
      `;

      document.body.appendChild(runCard);

      // Get the tag container BEFORE initialization
      const tagContainerBefore = document.getElementById('run-tags-myproject-testrun');
      const tagElementsBefore = tagContainerBefore.querySelectorAll('span:not(.text-text-muted)');
      const currentTagsBefore = Array.from(tagElementsBefore).map((el) => el.textContent.trim());

      // Verify tags were extracted correctly BEFORE initialization
      expect(currentTagsBefore).toEqual(['tag1', 'tag2']);

      // Now initialize tag editor (this is what runs-list.js does)
      const newTagEditor = new TagEditor();
      newTagEditor.init(tagContainerBefore, '/api/projects/myproject/runs/testrun/metadata', currentTagsBefore);

      // After initialization, the original container is REPLACED with tag-editor-wrapper
      // So querying by the original ID should fail
      const tagContainerAfter = document.getElementById('run-tags-myproject-testrun');
      expect(tagContainerAfter).toBeNull(); // The original container is gone!

      // The tag-editor-wrapper should exist and show the tags
      const wrapper = document.querySelector('.tag-editor-wrapper');
      expect(wrapper).toBeTruthy();

      const display = wrapper.querySelector('.tag-display');
      expect(display.textContent).toContain('tag1');
      expect(display.textContent).toContain('tag2');
      expect(display.textContent).not.toContain('No tags');

      // THIS IS THE BUG: If we try to re-initialize (e.g., after sorting),
      // the original container is gone, so we can't extract tags anymore!
      const containers = document.querySelectorAll('[id^="run-tags-"]');
      expect(containers.length).toBe(0); // No containers with run-tags-* ID exist!
    });
  });
});
