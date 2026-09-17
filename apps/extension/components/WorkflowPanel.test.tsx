// WorkflowPanel: stage display, SLA, role-appropriate actions, reason capture.
//
// Role gating here is presentation only — the server enforces the same rules —
// but offering a writer a button that will 403 is a bad experience, so it is
// pinned. The reason/override flow is pinned because losing it would let an
// editor scrap an article with no record of why.

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import type { WorkflowState } from '@/lib/types';
import type { AuthUser } from '@/lib/api';

const fetchWorkflow = vi.fn();
const transitionDocument = vi.fn();

vi.mock('@/lib/api', () => ({
  fetchWorkflow: (...a: unknown[]) => fetchWorkflow(...a),
  transitionDocument: (...a: unknown[]) => transitionDocument(...a),
}));

const { WorkflowPanel } = await import('./WorkflowPanel');

const user = (role: string): AuthUser => ({
  id: 1,
  email: `${role}@ties.org`,
  name: role,
  role,
});

const state = (over: Partial<WorkflowState> = {}): WorkflowState => ({
  status: 'drafting',
  next_states: ['submitted', 'under_review', 'reassigned', 'scrapped'],
  assigned_to: 'writer@ties.org',
  assigned_by: 'editor@ties.org',
  editor: 'editor@ties.org',
  word_min: 300,
  word_max: 350,
  assigned_at: null,
  submitted_at: null,
  approved_at: null,
  approved_by: '',
  override_reason: '',
  escalation_reason: '',
  blocking_reasons: [],
  sla: { phase: 'drafting', overdue: false, at_risk: false, hours_remaining: 14 },
  ...over,
});

function mount(me: AuthUser | null, data: WorkflowState = state()) {
  fetchWorkflow.mockResolvedValue(data);
  return render(<WorkflowPanel docId="doc-1" me={me} />);
}

beforeEach(() => {
  cleanup();
  fetchWorkflow.mockReset();
  transitionDocument.mockReset();
});

// --- display ---------------------------------------------------------------

describe('display', () => {
  it('renders nothing without a document id', () => {
    const { container } = render(<WorkflowPanel docId={null} me={user('writer')} />);
    expect(container.innerHTML).toBe('');
  });

  it('shows the current stage in words a writer recognises', async () => {
    mount(user('writer'));
    expect(await screen.findByText('Drafting')).toBeTruthy();
  });

  it('shows the SLA with hours remaining', async () => {
    mount(user('writer'));
    expect(await screen.findByText(/14h left/)).toBeTruthy();
  });

  it('flags an overdue phase', async () => {
    mount(user('writer'), state({
      sla: { phase: 'editing', overdue: true, at_risk: false, hours_remaining: -6 },
    }));
    expect(await screen.findByText(/6h overdue/)).toBeTruthy();
  });

  it('shows the assignment brief', async () => {
    mount(user('writer'));
    expect(await screen.findByText('writer@ties.org')).toBeTruthy();
    expect(screen.getByText('300–350')).toBeTruthy();
  });

  it('explains an untracked document instead of erroring', async () => {
    fetchWorkflow.mockRejectedValue(new Error('Document not tracked yet.'));
    render(<WorkflowPanel docId="doc-1" me={user('writer')} />);
    expect(await screen.findByText(/Run an evaluation to start tracking/)).toBeTruthy();
  });

  it('surfaces a real error', async () => {
    fetchWorkflow.mockRejectedValue(new Error('Backend unreachable'));
    render(<WorkflowPanel docId="doc-1" me={user('writer')} />);
    expect(await screen.findByText('Backend unreachable')).toBeTruthy();
  });
});

// --- role gating -----------------------------------------------------------

describe('role gating', () => {
  it('offers a writer only their own transitions', async () => {
    mount(user('writer'));
    expect(await screen.findByText('Submit for review')).toBeTruthy();
    expect(screen.queryByText('Start review')).toBeNull();
    expect(screen.queryByText('Scrap')).toBeNull();
    expect(screen.queryByText('GTG — Approve')).toBeNull();
  });

  it('offers an editor the full set', async () => {
    mount(user('editor'));
    expect(await screen.findByText('Start review')).toBeTruthy();
    expect(screen.getByText('Scrap')).toBeTruthy();
    expect(screen.getByText('Reassign')).toBeTruthy();
  });

  it('treats admin as an editor', async () => {
    mount(user('admin'));
    expect(await screen.findByText('Start review')).toBeTruthy();
  });

  it('tells a writer the rest is the editor’s to do', async () => {
    mount(user('writer'));
    expect(await screen.findByText(/editor's to take/)).toBeTruthy();
  });
});

// --- transitions -----------------------------------------------------------

describe('transitions', () => {
  it('submits directly when no reason is needed', async () => {
    mount(user('writer'));
    transitionDocument.mockResolvedValue(state({ status: 'submitted' }));
    (await screen.findByText('Submit for review')).click();
    await waitFor(() =>
      expect(transitionDocument).toHaveBeenCalledWith('doc-1', 'submitted', {}),
    );
  });

  it('requires a written reason before scrapping', async () => {
    mount(user('editor'));
    (await screen.findByText('Scrap')).click();
    // The transition must not fire until a reason is given.
    expect(transitionDocument).not.toHaveBeenCalled();
    expect(await screen.findByText(/Why are you scrapping this/)).toBeTruthy();
  });

  it('requires an override reason when approval is blocked', async () => {
    mount(user('editor'), state({
      status: 'submitted',
      next_states: ['approved'],
      blocking_reasons: ['AI and plagiarism checks have not been recorded (SOP §4).'],
    }));
    (await screen.findByText('GTG — Approve')).click();
    expect(transitionDocument).not.toHaveBeenCalled();
    expect(await screen.findByText(/Reason for approving despite/)).toBeTruthy();
  });

  it('approves straight through when nothing is blocking', async () => {
    mount(user('editor'), state({ status: 'submitted', next_states: ['approved'] }));
    transitionDocument.mockResolvedValue(state({ status: 'approved' }));
    (await screen.findByText('GTG — Approve')).click();
    await waitFor(() =>
      expect(transitionDocument).toHaveBeenCalledWith('doc-1', 'approved', {}),
    );
  });

  it('shows blocking reasons to an editor', async () => {
    mount(user('editor'), state({
      blocking_reasons: ['Plagiarism is 22% — the SOP requires under 15%.'],
    }));
    expect(await screen.findByText(/Plagiarism is 22%/)).toBeTruthy();
  });

  it('does not nag a writer with the editor’s checklist', async () => {
    mount(user('writer'), state({ blocking_reasons: ['Something for the editor'] }));
    await screen.findByText('Drafting');
    expect(screen.queryByText('Before signing off')).toBeNull();
  });
});

// --- recorded outcomes -----------------------------------------------------

describe('recorded outcomes', () => {
  it('shows who approved and when', async () => {
    mount(user('writer'), state({
      status: 'approved',
      next_states: [],
      approved_by: 'ed@ties.org',
      approved_at: '2026-09-17T10:00:00Z',
    }));
    expect(await screen.findByText(/ed@ties.org/)).toBeTruthy();
  });

  it('shows an override reason prominently', async () => {
    mount(user('editor'), state({
      status: 'approved',
      next_states: [],
      override_reason: 'Time-critical; checks run manually.',
    }));
    expect(await screen.findByText(/Time-critical/)).toBeTruthy();
  });

  it('shows why something was scrapped', async () => {
    mount(user('writer'), state({
      status: 'scrapped',
      next_states: [],
      escalation_reason: 'Fails factual standards.',
    }));
    expect(await screen.findByText(/Fails factual standards/)).toBeTruthy();
  });
});
