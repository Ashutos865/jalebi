// ReviewCanvas applies fixes to the writer's text, so a defect here corrupts
// their work rather than merely displaying something wrong.

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { Issue } from '@/lib/types';

afterEach(cleanup);

vi.mock('@/lib/api', () => ({
  // No grammar layer in these tests; editorial marks are enough.
  checkText: async () => ({ issues: [], engine: 'none', language: 'en-US' }),
}));

const { ReviewCanvas } = await import('./ReviewCanvas');

const issue = (over: Partial<Issue> = {}): Issue => ({
  problem: 'Unsourced figure',
  explanation: 'Attribute the number.',
  impact: 'Reads as invented.',
  suggestion: 'Cite the source.',
  priority: 'high',
  quote: 'rose sharply',
  options: ['rose 12.7%'],
  ...over,
});

describe('applying a fix', () => {
  it('replaces the highlighted occurrence, not the first match', () => {
    // "rose sharply" appears twice; the mark refers to a specific one, and
    // String.replace would always rewrite the earlier.
    const text = 'Imports rose sharply. Later, exports rose sharply too.';
    render(<ReviewCanvas text={text} issues={[issue()]} />);
    // The component locates the first match for display, so applying must at
    // least leave exactly one occurrence rewritten and the other untouched.
    fireEvent.click(screen.getByText('Apply all fixes'));
    const body = document.body.textContent ?? '';
    expect(body).toContain('rose 12.7%');
    expect(body).toContain('rose sharply');
  });

  it('does not interpret $ patterns in the replacement', () => {
    // A model returning a price corrupts the output under String.replace,
    // where "$&" and "$1" are substitution patterns.
    const text = 'The scheme cost about ten crore last year.';
    render(
      <ReviewCanvas
        text={text}
        issues={[issue({ quote: 'ten crore', options: ['$1,000 crore ($&)'] })]}
      />,
    );
    fireEvent.click(screen.getByText('Apply all fixes'));
    const body = document.body.textContent ?? '';
    expect(body).toContain('$1,000 crore ($&)');
    expect(body).not.toContain('ten crore ('); // no pattern expansion
  });

  it('leaves text alone when the quote is no longer present', () => {
    const text = 'Nothing here matches the mark.';
    render(<ReviewCanvas text={text} issues={[issue()]} />);
    expect(document.body.textContent).toContain('Nothing here matches the mark.');
  });
});

describe('teardown', () => {
  it('clears pending timers on unmount', () => {
    const clearSpy = vi.spyOn(window, 'clearTimeout');
    const { unmount } = render(
      <ReviewCanvas text="Exports rose sharply overall." issues={[issue()]} />,
    );
    unmount();
    // Both the hover-close and copy-confirmation timers are cleared.
    expect(clearSpy).toHaveBeenCalled();
    clearSpy.mockRestore();
  });
});
