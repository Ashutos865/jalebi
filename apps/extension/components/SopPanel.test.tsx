// SopPanel rendering rules. The important one: the panel must stay hidden for
// documents that are not TIES assignments, so an ordinary draft is not covered
// in red failures it can never satisfy.

import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { SopPanel } from './SopPanel';
import type { SopCheckItem, SopComplianceReport } from '@/lib/types';

const check = (over: Partial<SopCheckItem> = {}): SopCheckItem => ({
  name: 'SOP header block present',
  passed: true,
  detail: '',
  severity: 'required',
  ...over,
});

const report = (over: Partial<SopComplianceReport> = {}): SopComplianceReport => ({
  checked: true,
  compliant: true,
  checks: [check()],
  header_present: true,
  header_fields: {},
  missing_fields: [],
  word_count: 320,
  word_min: 300,
  word_max: 350,
  reference_urls: [],
  ...over,
});

const html = (sop: SopComplianceReport) =>
  renderToStaticMarkup(<SopPanel sop={sop} />);

describe('SopPanel', () => {
  it('renders nothing when the document has no SOP header', () => {
    expect(html(report({ checked: false }))).toBe('');
  });

  it('shows a compliant badge when every required check passes', () => {
    const out = html(report());
    expect(out).toContain('SOP compliant');
    expect(out).toContain('1 of 1 checks passed');
  });

  it('counts only blocking failures in the badge', () => {
    const out = html(
      report({
        compliant: false,
        checks: [
          check({ name: 'Word count within 300–350', passed: false }),
          check({ name: 'Uses lists', passed: false, severity: 'advisory' }),
          check({ name: 'References present', passed: false }),
        ],
      }),
    );
    // 3 failures, but only 2 are required.
    expect(out).toContain('2 to fix');
  });

  it('lists failures before passes', () => {
    const out = html(
      report({
        compliant: false,
        checks: [
          check({ name: 'AAA passing check', passed: true }),
          check({ name: 'ZZZ failing check', passed: false }),
        ],
      }),
    );
    expect(out.indexOf('ZZZ failing check')).toBeLessThan(
      out.indexOf('AAA passing check'),
    );
  });

  it('shows the detail text that tells the writer what to do', () => {
    const out = html(
      report({
        compliant: false,
        checks: [
          check({
            name: 'Word count within 300–350',
            passed: false,
            detail: '401 words — 300–350 required; trim ~51.',
          }),
        ],
      }),
    );
    expect(out).toContain('trim ~51');
  });

  it('omits the word count when no window applies', () => {
    const out = html(report({ word_min: null, word_max: null }));
    expect(out).not.toContain('words');
  });
});
