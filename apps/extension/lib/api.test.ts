// Error-detail formatting.
//
// FastAPI returns `detail` as a string for an HTTPException but as an array of
// validation objects for a 422. Passing that array to React throws "Objects are
// not valid as a React child" and blanks the whole panel, so it is normalised
// to text before it ever reaches the UI.

import { describe, expect, it, vi } from 'vitest';

vi.stubGlobal('chrome', {
  storage: { local: { get: async () => ({}), set: async () => {} } },
});

const { __formatDetailForTest: formatDetail } = await import('./api');

describe('formatDetail', () => {
  it('passes a plain string through', () => {
    expect(formatDetail('Document not tracked yet.')).toBe(
      'Document not tracked yet.',
    );
  });

  it('renders a FastAPI 422 array as readable text', () => {
    const detail = [
      { loc: ['body', 'ai_percent'], msg: 'Input should be less than or equal to 100' },
      { loc: ['body', 'plagiarism_percent'], msg: 'Field required' },
    ];
    const out = formatDetail(detail);
    expect(out).toContain('ai_percent: Input should be less than or equal to 100');
    expect(out).toContain('plagiarism_percent: Field required');
    expect(out).not.toContain('[object Object]');
  });

  it('drops the noisy "body" prefix from the field path', () => {
    expect(formatDetail([{ loc: ['body', 'status'], msg: 'Field required' }])).toBe(
      'status: Field required',
    );
  });

  it('copes with a message that has no location', () => {
    expect(formatDetail([{ msg: 'Something went wrong' }])).toBe(
      'Something went wrong',
    );
  });

  it('never returns an object', () => {
    for (const input of [
      { unexpected: 'shape' },
      [{ no: 'msg' }],
      null,
      42,
    ]) {
      expect(typeof formatDetail(input)).toBe('string');
    }
  });
});
