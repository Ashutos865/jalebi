import { describe, it, expect } from 'vitest';
import { parseDocId, isGoogleDocUrl, cleanTitle } from './doc';

describe('parseDocId', () => {
  it('extracts the id from a Google Docs URL', () => {
    expect(
      parseDocId('https://docs.google.com/document/d/1AbC_def-123/edit#heading'),
    ).toBe('1AbC_def-123');
  });
  it('returns null for non-doc URLs', () => {
    expect(parseDocId('https://docs.google.com/spreadsheets/d/xyz')).toBeNull();
    expect(parseDocId('https://example.com')).toBeNull();
  });
});

describe('isGoogleDocUrl', () => {
  it('matches only document URLs', () => {
    expect(isGoogleDocUrl('https://docs.google.com/document/d/abc/edit')).toBe(true);
    expect(isGoogleDocUrl('https://docs.google.com/presentation/d/abc')).toBe(false);
    expect(isGoogleDocUrl(undefined)).toBe(false);
  });
});

describe('cleanTitle', () => {
  it('strips the Google Docs suffix', () => {
    expect(cleanTitle('My Article - Google Docs')).toBe('My Article');
    expect(cleanTitle('Plain title')).toBe('Plain title');
  });
});
