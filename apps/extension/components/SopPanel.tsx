// TIES Content SOP compliance — the mechanical checks (header block, word
// window, structure, references), shown above the editorial score.
//
// Kept visually distinct from the scorecard on purpose: these answer "did you
// follow the procedure?", not "is the writing good?". A piece can be excellent
// prose and still be missing its Instagram handle.

import { SectionPill, PILL } from './vitals';
import type { SopCheckItem, SopComplianceReport } from '@/lib/types';

const TONE = { bg: '#E0F2FE', fg: '#2E90FA', emoji: 'steps' as const };

function CheckRow({ check }: { check: SopCheckItem }) {
  const advisory = check.severity === 'advisory';
  const mark = check.passed ? '✓' : advisory ? '!' : '✕';
  const colour = check.passed
    ? 'text-[#17B26A]'
    : advisory
      ? 'text-[#E8820C]'
      : 'text-[#F04438]';

  return (
    <li className="flex gap-2 py-1">
      <span
        aria-hidden
        className={`mt-[1px] w-3 shrink-0 text-center text-[13px] font-bold ${colour}`}
      >
        {mark}
      </span>
      <span className="min-w-0">
        <span
          className={`text-[13px] ${check.passed ? 'opacity-70' : 'font-semibold'}`}
        >
          {check.name}
        </span>
        {check.detail && (
          <span className="block text-[12px] leading-snug opacity-60">
            {check.detail}
          </span>
        )}
      </span>
    </li>
  );
}

export function SopPanel({ sop }: { sop: SopComplianceReport }) {
  // No SOP header → not a TIES assignment. Showing a wall of failures on an
  // ordinary draft would be noise, so the panel stays hidden.
  if (!sop?.checked) return null;

  const failures = sop.checks.filter((c) => !c.passed);
  const blocking = failures.filter((c) => c.severity === 'required');
  const passed = sop.checks.length - failures.length;

  const status = sop.compliant
    ? { text: 'SOP compliant', bg: '#DCFAE6', fg: '#17B26A' }
    : {
        text: `${blocking.length} to fix`,
        bg: '#FFE7E5',
        fg: '#F04438',
      };

  return (
    <section className="card p-4">
      <div className="flex items-center justify-between gap-2">
        <SectionPill label="SOP compliance" tone={PILL.steps ?? TONE} />
        <span
          style={{ background: status.bg, color: status.fg }}
          className="rounded-full px-2 py-0.5 text-[11px] font-bold"
        >
          {status.text}
        </span>
      </div>

      <p className="mt-2.5 text-[12px] opacity-60">
        {passed} of {sop.checks.length} checks passed
        {sop.word_min != null || sop.word_max != null
          ? ` · ${sop.word_count} words`
          : ''}
      </p>

      <ul className="mt-1.5">
        {/* Failures first — that is what the writer has to act on. */}
        {failures.map((c) => (
          <CheckRow key={c.name} check={c} />
        ))}
        {sop.checks
          .filter((c) => c.passed)
          .map((c) => (
            <CheckRow key={c.name} check={c} />
          ))}
      </ul>
    </section>
  );
}
