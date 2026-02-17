import { describe, expect, test } from 'vitest';
import {
  EMPTY_NOTE_PLACEHOLDER,
  createSaveNoteRequestBody,
  extractNoteFromResponse,
  extractNoteText,
  formatNoteForDisplay,
  getEditButtonHTML,
  isNoteEmpty,
} from '../../src/aspara/dashboard/static/js/note-editor-utils.js';

describe('EMPTY_NOTE_PLACEHOLDER', () => {
  test('has expected value', () => {
    expect(EMPTY_NOTE_PLACEHOLDER).toBe('Add note...');
  });
});

describe('formatNoteForDisplay', () => {
  test('returns placeholder span for empty note', () => {
    const result = formatNoteForDisplay('');
    expect(result).toContain('text-text-muted');
    expect(result).toContain('italic');
    expect(result).toContain(EMPTY_NOTE_PLACEHOLDER);
  });

  test('returns placeholder span for null note', () => {
    const result = formatNoteForDisplay(null);
    expect(result).toContain(EMPTY_NOTE_PLACEHOLDER);
  });

  test('returns placeholder span for undefined note', () => {
    const result = formatNoteForDisplay(undefined);
    expect(result).toContain(EMPTY_NOTE_PLACEHOLDER);
  });

  test('escapes HTML in note content', () => {
    const result = formatNoteForDisplay('<script>alert("xss")</script>');
    expect(result).not.toContain('<script>');
    expect(result).toContain('&lt;script&gt;');
  });

  test('converts newlines to br tags', () => {
    const result = formatNoteForDisplay('line1\nline2\nline3');
    expect(result).toBe('line1<br>line2<br>line3');
  });

  test('handles note with both HTML and newlines', () => {
    const result = formatNoteForDisplay('<b>bold</b>\nnew line');
    expect(result).toContain('&lt;b&gt;');
    expect(result).toContain('<br>');
  });

  test('preserves normal text', () => {
    const result = formatNoteForDisplay('This is a normal note');
    expect(result).toBe('This is a normal note');
  });
});

describe('isNoteEmpty', () => {
  test('returns true for empty string', () => {
    expect(isNoteEmpty('')).toBe(true);
  });

  test('returns true for null', () => {
    expect(isNoteEmpty(null)).toBe(true);
  });

  test('returns true for undefined', () => {
    expect(isNoteEmpty(undefined)).toBe(true);
  });

  test('returns true for whitespace only', () => {
    expect(isNoteEmpty('   ')).toBe(true);
    expect(isNoteEmpty('\t\n')).toBe(true);
  });

  test('returns true for placeholder text', () => {
    expect(isNoteEmpty(EMPTY_NOTE_PLACEHOLDER)).toBe(true);
  });

  test('returns true for placeholder with whitespace', () => {
    expect(isNoteEmpty(`  ${EMPTY_NOTE_PLACEHOLDER}  `)).toBe(true);
  });

  test('returns false for actual content', () => {
    expect(isNoteEmpty('Some note')).toBe(false);
  });

  test('returns false for content with whitespace', () => {
    expect(isNoteEmpty('  Some note  ')).toBe(false);
  });
});

describe('extractNoteText', () => {
  test('returns empty string for empty input', () => {
    expect(extractNoteText('')).toBe('');
  });

  test('returns empty string for null', () => {
    expect(extractNoteText(null)).toBe('');
  });

  test('returns empty string for undefined', () => {
    expect(extractNoteText(undefined)).toBe('');
  });

  test('returns empty string for placeholder', () => {
    expect(extractNoteText(EMPTY_NOTE_PLACEHOLDER)).toBe('');
  });

  test('returns trimmed content for actual note', () => {
    expect(extractNoteText('  My note  ')).toBe('My note');
  });

  test('preserves internal whitespace', () => {
    expect(extractNoteText('Note with   spaces')).toBe('Note with   spaces');
  });
});

describe('createSaveNoteRequestBody', () => {
  test('creates JSON with notes field', () => {
    const result = createSaveNoteRequestBody('My note');
    expect(result).toBe('{"notes":"My note"}');
  });

  test('handles empty note', () => {
    const result = createSaveNoteRequestBody('');
    expect(result).toBe('{"notes":""}');
  });

  test('handles note with special characters', () => {
    const result = createSaveNoteRequestBody('Note with "quotes" and \\backslash');
    const parsed = JSON.parse(result);
    expect(parsed.notes).toBe('Note with "quotes" and \\backslash');
  });

  test('handles multiline note', () => {
    const result = createSaveNoteRequestBody('Line 1\nLine 2');
    const parsed = JSON.parse(result);
    expect(parsed.notes).toBe('Line 1\nLine 2');
  });
});

describe('extractNoteFromResponse', () => {
  test('extracts notes from response', () => {
    const result = extractNoteFromResponse({ notes: 'My note' });
    expect(result).toBe('My note');
  });

  test('returns empty string when notes is undefined', () => {
    const result = extractNoteFromResponse({});
    expect(result).toBe('');
  });

  test('returns empty string when notes is null', () => {
    const result = extractNoteFromResponse({ notes: null });
    expect(result).toBe('');
  });

  test('handles empty notes', () => {
    const result = extractNoteFromResponse({ notes: '' });
    expect(result).toBe('');
  });

  test('handles response with other fields', () => {
    const result = extractNoteFromResponse({ notes: 'Note', id: 123, status: 'ok' });
    expect(result).toBe('Note');
  });
});

describe('getEditButtonHTML', () => {
  test('returns HTML with SVG icon', () => {
    const result = getEditButtonHTML();
    expect(result).toContain('<svg');
    expect(result).toContain('</svg>');
  });

  test('returns HTML with Edit text', () => {
    const result = getEditButtonHTML();
    expect(result).toContain('Edit');
  });

  test('has proper SVG symbol reference', () => {
    const result = getEditButtonHTML();
    expect(result).toContain('<use href="#icon-edit">');
  });
});
