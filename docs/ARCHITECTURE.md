# Jalebi — Architecture

Why the system is shaped the way it is. Kept lean and current: where a decision has
been reversed, the reversal is recorded rather than the original intent.

---

## 1. What Jalebi is

An editorial quality-assurance system. It behaves like a managing editor: it evaluates
content against an editorial standard, explains weaknesses, recommends fixes, and rules
on publication readiness. It **coaches**; it does not rewrite.

Scale target: roughly 100 internal users. This is an organisational tool, so it
optimises for maintainability, editorial quality and explainability — not for
hyperscale infrastructure.

---

## 2. System shape

```
┌───────────────────────────┐      HTTPS/JSON       ┌──────────────────────────────┐
│  Chrome extension (MV3)   │ ────────────────────▶ │  FastAPI                     │
│  WXT · React · Tailwind   │  POST /api/evaluate   │                              │
│                           │                       │  ┌────────────────────────┐  │
│  content script:          │ ◀──────────────────── │  │ HybridEvaluator        │  │
│   detect Google Doc       │   EvaluationResult    │  │  rules  (deterministic)│  │
│   extract text via export │                       │  │  + AI judgment (opt.)  │  │
│  side panel (React):      │                       │  └───────────┬────────────┘  │
│   score · SOP · workflow  │                       │              │               │
└───────────────────────────┘                       │      ┌───────▼────────┐      │
                                                    │      │ scoring engine │      │
                                                    │      │ blend · caps   │      │
                                                    │      │ bands · issues │      │
                                                    │      └────────────────┘      │
                                                    └──────────────────────────────┘
```

---

## 3. Key decisions

### 3.1 Google Docs text extraction — the export endpoint

Modern Google Docs renders to `<canvas>`, so the text is **not in the DOM** and cannot
be scraped. Two options existed:

- **Annotated Canvas API** — how Grammarly draws inline underlines. Requires an explicit
  whitelist grant from Google. Out of our control; rejected.
- **Export endpoint** — `docs.google.com/document/d/{id}/export?format=txt`, fetched by
  a content script with the user's existing session. No OAuth consent, no whitelist.
  **Chosen.**

Consequence: Jalebi's feedback lives in the sidebar and quotes the passages it refers
to, rather than marking up the document. The right trade for an internal tool, and it
removes a dependency we cannot influence.

### 3.2 Scoring is deterministic first, AI second

The score is a blend, per dimension, of a **rules engine** and **model judgment**. Each
dimension carries an `alpha` — its deterministic share. Overall, about **72%** of the
score is reproducible with no API key at all.

This is the most consequential decision in the system, and it is deliberate:

- **Editors will not trust a number that changes between runs.** The same text always
  produces the same score.
- **It works with no provider configured**, which is how every test runs and how a
  newsroom with no budget can use it.
- **A failing provider degrades rather than breaks.** A timeout or an unparseable reply
  falls back to rules-only and still returns a scorecard.

`app/scoring/reasoning.py` is what makes this viable for the dimensions that look
subjective. Rather than pattern-matching vocabulary, it measures the *structure* of
reasoning: conclusions bound to stated premises, causal chains, comparison,
acknowledged counter-argument, concrete specifics, and filler that announces
significance without supplying it. Every signal is density-capped so padding cannot
inflate a score.

### 3.3 Hard caps override everything

Some failures should not be survivable by scoring well elsewhere. A fabricated
quotation caps the result at 0; a fabricated statistic at 20; an unsupported claim at
50. Caps are applied after the weighted blend, and the triggering passage is quoted
back.

### 3.4 One evaluator

`HybridEvaluator` handles every provider, including `mock` (the same class with no
client, so rules-only). An earlier design had separate `MockEvaluator`,
`ClaudeEvaluator`, `LLMEvaluator` and `MultiAgentEvaluator` classes behind an
`Evaluator` interface; all four became unreachable when the hybrid engine landed and
have been deleted, along with the `app/rubrics` weighting vocabulary that only they
read. The `Evaluator` ABC remains as the seam.

### 3.5 Fact-checking surfaces, never verifies

`POST /api/factcheck` returns claims ranked by how badly they need review, with the
nearest citation attached. Jalebi does not fetch URLs or judge whether a source supports
a claim. It cannot do either reliably, and a tool that appeared to would be trusted and
wrong — the failure mode the feature exists to prevent.

### 3.6 Integrity percentages are recorded, not estimated

AI-content and plagiarism figures come from the editor's own tooling and are stored on
the document. Jalebi applies the thresholds and gates sign-off. It does not run AI
detection: published research puts commercial detectors' false-positive rate on
non-native English writing at 61.3%, and a wrong result here lands in a process that
affects someone's certificate and reference. See [PRODUCT.md](../PRODUCT.md) §2.2.

### 3.7 Extension framework — WXT

Vite-based, first-class MV3 and side-panel support, not locked to a bundler.

### 3.8 Backend — FastAPI

Typed request/response via Pydantic, async, OpenAPI for free.

---

## 4. The evaluation contract

The Pydantic models in `apps/backend/app/schemas/evaluation.py` are the single source of
truth; `apps/extension/lib/types.ts` mirrors them by hand. Shape, abridged:

```jsonc
{
  "overall_score": 76,
  "publication_ready": false,
  "publication_readiness": "Needs Minor Revision",
  "content_type": "analysis",
  "summary": "...",
  "categories": [
    { "name": "Research Accuracy", "key": "accuracy", "score": 85, "weight": 0.30,
      "issues": [ { "problem": "...", "explanation": "...", "impact": "...",
                    "suggestion": "...", "priority": "high", "quote": "..." } ] }
  ],
  "critical_issues": [ /* surfaced first */ ],
  "strengths": [ "..." ],
  "next_steps": [ "..." ],
  "sop": { "checked": true, "compliant": false, "checks": [ /* ... */ ] },
  "meta": { "evaluator": "mock", "word_count": 324, "duration_ms": 41 }
}
```

Every issue carries problem, explanation, impact, suggestion, priority and the quoted
passage, so feedback is always actionable and points at real text.

---

## 5. Scoring dimensions

| Dimension | Weight | Rule share | What the rules measure |
|---|---|---|---|
| Research Accuracy | 0.30 | 0.75 | Unsourced statistics, attribution, source tier |
| Original Insight | 0.20 | 0.45 | Inference, comparison, counter-argument, filler |
| Narrative Structure | 0.15 | 0.70 | Paragraphing, sentence-length variance, transitions |
| Depth | 0.10 | 0.70 | Causal chains, mechanism vocabulary, specificity |
| Credibility & Sourcing | 0.10 | 0.95 | Source tiers, citation density |
| Writing Quality | 0.10 | 0.95 | House style, AI clichés, repetition |
| Headline | 0.05 | 0.85 | Clickbait, headline/body alignment |

Weights vary by content type (breaking news leans on accuracy; opinion on insight) and
are tunable per type from the admin panel. An override is validated, normalised to sum
to 1.0, and reported back with both the requested and effective values so an admin is
never shown a number they did not enter.

---

## 6. The production loop

`app/workflow/states.py` models the editorial process as an explicit state machine:

```
assigned → drafting → submitted → under_review → revising → approved → published
                  ↘ reassigned / scrapped (from any live state, reason required)
```

Transitions are validated, so a piece cannot jump from assigned to approved. Editor-only
transitions are enforced server-side. Each phase carries the SOP's own deadline windows,
and `phase_started_at` resets on every transition that opens a new one, so "overdue"
always refers to the current phase.

Approval is never blocked. The SOP gives the editor final say, so failing checks surface
as `blocking_reasons` and an editor who signs off anyway records a written reason, which
is audited and sent to the team lead.

---

## 7. Testing

- **Backend:** 349 tests. Deterministic because the mock provider is rules-only, so the
  suite needs no API key, costs nothing and never flakes on a network call. No test
  makes a live provider call — a deliberate trade of end-to-end coverage for
  reproducibility.
- **Extension:** 60 tests under jsdom, covering the DOM-driven modules (inline checker,
  editable-field detection, review canvas, panels) as well as pure helpers.
- **The standard applied throughout:** a fix ships with a test that **fails against the
  pre-fix code**. Several bugs in this codebase were found by writing that test first.

---

## 8. Security posture

API keys live only on the backend. JWT with explicit `HS256`, role-based access
(writer / editor / admin) checked against the database row rather than the token claim,
so a demotion takes effect immediately. Audit logging on privileged actions. All queries
use bound parameters.

In production the app **refuses to start** on unsafe configuration — the published
default signing key, an open dev-login, or wildcard CORS. See
[CONFIGURATION.md](CONFIGURATION.md#the-production-gate).

Known limitation: the inline grammar checker runs on all sites. It never reads password
fields, payment details or one-time codes, but broad host access remains the strongest
argument against publishing the extension as-is.
