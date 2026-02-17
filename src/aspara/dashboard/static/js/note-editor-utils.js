/**
 * Pure utility functions for note editor
 * These functions have no side effects and are easy to test
 */

import { ICON_EDIT, escapeHtml } from './html-utils.js';

/**
 * Placeholder text shown when note is empty
 */
export const EMPTY_NOTE_PLACEHOLDER = 'Add note...';

/**
 * Format note content for display (escape HTML and convert newlines)
 * @param {string} note - Raw note text
 * @returns {string} HTML-safe note with newlines as <br>
 */
export function formatNoteForDisplay(note) {
  if (!note) {
    return `<span class="text-text-muted italic">${EMPTY_NOTE_PLACEHOLDER}</span>`;
  }
  return escapeHtml(note).replace(/\n/g, '<br>');
}

/**
 * Check if note content is empty or just placeholder
 * @param {string} text - Text content to check
 * @returns {boolean} True if note is effectively empty
 */
export function isNoteEmpty(text) {
  if (!text) return true;
  const trimmed = text.trim();
  return trimmed === '' || trimmed === EMPTY_NOTE_PLACEHOLDER;
}

/**
 * Extract actual note text from content element text
 * @param {string} contentText - Text content from note display element
 * @returns {string} Actual note text (empty string if placeholder)
 */
export function extractNoteText(contentText) {
  if (!contentText) return '';
  const trimmed = contentText.trim();
  return trimmed === EMPTY_NOTE_PLACEHOLDER ? '' : trimmed;
}

/**
 * Create request body for saving note
 * @param {string} note - Note text
 * @returns {string} JSON string for request body
 */
export function createSaveNoteRequestBody(note) {
  return JSON.stringify({ notes: note });
}

/**
 * Parse save note response
 * @param {Object} responseData - Response data from API
 * @returns {string} Note text from response
 */
export function extractNoteFromResponse(responseData) {
  return responseData.notes || '';
}

/**
 * Create edit button HTML
 * @returns {string} Edit button HTML
 */
export function getEditButtonHTML() {
  return `${ICON_EDIT} Edit`;
}
