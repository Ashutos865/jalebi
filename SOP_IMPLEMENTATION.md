# Implementing the TIES Content SOP in Jalebi

An analysis of what the SOP requires, what Jalebi already does, and what to build —
in the order that delivers the most value per unit of work.

---

## 1. The key insight

Jalebi today grades **prose quality**. The SOP governs **a production process**, of
which prose quality is one part. The gap is not mainly in the scoring engine — it is
that Jalebi has no concept of an *assignment*, a *deadline*, or a *handoff*.

That leads to a clean split, and it should drive the build order:

| | What it covers | Jalebi's fit |
|---|---|---|
| **A. Machine-checkable** | Header block, formatting, word limits, references, subheadings | **Strong.** Deterministic rules, near-zero risk, high daily value |
| **B. Judgment, assisted** | Fact-checking, source quality, nation-first mandate | **Partial.** Jalebi can *surface* and *prioritise*; a human still decides |
| **C. Process & workflow** | 24–30h loop, deadlines, GTG sign-off, escalation | **Absent.** This is a tracker, not an editor — biggest build, clearest need |

**Recommendation: build A first.** It is small, it is unambiguous, and it removes the
most repetitive part of the editor's job — the mechanical compliance pass they
currently do by hand on every draft.

---

## 2. What already exists

More than expected. Verified against the code, not the docs:

| SOP requirement | Status | Where |
|---|---|---|
| TIES content categories | **Done** | `breaking_news`, `analysis`, `investigative`, `opinion` in `schemas/evaluation.py:23-26`, surfaced in the extension at `lib/contentTypes.ts:6-9` |
| Per-category weighting | **Done** | `constitution.py:62-67` — breaking news weights accuracy 40%, opinion weights insight 30% |
| Source hierarchy | **Partial** | `constitution.py:118-130` — 6 tiers exist and are scored (`rules.py:171-190`). But of the outlets the SOP names, **only *The Hindu* is listed** — *Indian Express*, *Firstpost* and *Google Scholar* are all absent. Matching is also substring-on-full-text, not domain parsing, so the bare word "university" anywhere scores Tier 3 |
| Fabrication / unsourced claims | **Done** | `HARD_CAPS` at `constitution.py:88-95`: fabricated quote caps the score at 0, fabricated statistic at 20 |
| Unattributed claim detection | **Done** | `analysis/analyzers.py:80-92` — flags quantitative claims with no nearby source |
| Bias & absolutes | **Done** | `analyzers.py:94-106`, `constitution.py:141` |
| Article status tracking | **Done** | `Document.status` (draft/under_review/finalized/published), `editor`, `published_for`, `co_authors` — `db/models.py`, editable via `PATCH /api/documents/{id}` |
| Roles | **Done** | writer / editor / admin (`db/models.py:15-18`) maps onto author / editor / team lead |
| Pass/fail checklist UI | **Done** | `CheckItem` pattern, 10 checks in `scoring/rules.py` — the natural home for SOP checks |

**The foundation is already SOP-shaped.** This is extension work, not a rebuild.

---

## 3. What is missing

Verified absent in code:

| SOP requirement | Status |
|---|---|
| Header block parsing / validation | **Absent** |
| Word-count limits (300–350) | Counted at `rules.py:96`, **never enforced** |
| Formatting (Times New Roman 12pt, 1.5, justified) | **Absent** — and see §6, it is not recoverable from the text export |
| References section at the bottom | **Absent** as a structural check |
| Subheading / H2-H3 structure | **Absent** — no structural detection at all, despite "no plain text" being mandatory |
| AI % and plagiarism % caps | **Absent** — no detection, and see §6 |
| Nation-first mandate | **Absent** as a specific rule (generic neutrality only) |
| Deadlines, 24–30h loop, assignment briefs | **Absent** — no `deadline`, `assigned_at` or `due_at` field anywhere |
| GTG sign-off, escalation, reassignment | **Absent** |

---

## 4. The engine currently penalises SOP compliance

This is the most important finding in this document, and it must be settled before any
SOP feature is built — otherwise the new checks and the existing scorer will pull in
opposite directions.

Two rules in the scoring engine directly contradict the SOP:

- **`rules.py:238-246` penalises bullet lists** — −10 to writing quality when there
  are ≥6 bullet lines, with the message *"TIES prefers flowing paragraphs over
  fragmented bullet lists."* The SOP **mandates** "innovative bullet points, numbered
  lists, or key takeaways."
- **`rules.py:309-312` rewards length** — +10 depth above 800 words, +10 more above
  1500. The SOP caps standard short-form articles at **300–350 words**.

Measured on the real engine — an SOP-perfect article versus one that ignores the SOP:

```
SOP-perfect (340w + bulleted takeaways)   writing= 90   depth=55
Long prose  (1250w, no bullets)           writing=100   depth=65
```

**The article that follows the SOP scores lower on both dimensions.** A writer doing
exactly what the SOP demands is marked down for it.

These rules are inherited from the Editorial Constitution
(`ties_constitution.md:122`), which is a *different document* from this SOP. Someone
has to decide which wins:

- **Scope the rules by content type** — keep "prefer prose" and the length reward for
  long-form (`research_paper`, `investigative`), drop both for SOP short-form. This is
  my recommendation: it honours both documents where each applies.
- Or amend the Constitution to match the SOP outright.

Either way it is a **decision, not a code change**, and it belongs to whoever owns
the editorial standard — not to me.

---

## 5. A second finding worth acting on first

**The SOP header block currently corrupts the score.** Jalebi extracts the whole
document and grades all of it, header included. I measured this on the real engine
with a compliant header plus a short body:

```
word_count WITH header   : 112
word_count WITHOUT header:  72      → header inflates by 40 words

dim_scores WITH   : {... 'sourcing':  76, ... 'headline': 90}
dim_scores WITHOUT: {... 'sourcing': 100, ... 'headline': 60}
```

Two real consequences:

1. **Word count is inflated by ~40 words.** Against a 300–350 limit, that alone can
   push a compliant article out of range — a check the SOP treats as strict.
2. **Scores move in both directions.** `sourcing` drops 100→76 (the header's bare
   URLs and labels dilute the signal) while `headline` jumps 60→90, because the
   `HEADING:` line accidentally satisfies the headline check.

So the *better* a writer follows the SOP, the more distorted their score becomes.

This makes header parsing a **correctness fix, not just a feature** — and it is the
natural first task, because everything else in Part A depends on knowing where the
metadata ends and the article begins.

Good news: the extension only calls `.trim()` on extraction (`lib/doc.ts:38`), so the
full header arrives at the backend intact and is fully parseable.

---

## 6. Two things to be honest about

I would rather flag these now than have them surface as failures later.

**Formatting (Times New Roman, 12pt, 1.5 spacing, justified) cannot be checked from
the current extraction.** Jalebi fetches the doc via the plain-text export endpoint,
which discards all formatting by definition. Options:

- Use the **Google Docs API** (`documents.get`), which returns `textStyle` and
  `paragraphStyle` — real, but needs the OAuth scope the extension already declares.
- Or leave formatting to the human editor and don't pretend to check it.

My recommendation: **defer it.** It is the lowest-value, highest-plumbing item, and
a wrong "formatting is fine" is worse than no check.

**AI % and plagiarism % should not be guessed.** The SOP names specific tools
(Quillbot, CopyLeaks, SmallSEOTools, DupliChecker) precisely because these need a
real detector. Jalebi should **record and gate on** the numbers an editor obtained,
not invent them — a homegrown AI-detector would be unreliable and the false
accusations would be serious. Store `ai_percent` / `plagiarism_percent` on the
document, block sign-off until both are filled and under the caps.

---

## 7. Proposed build

### Phase 1 — SOP compliance checks (highest value, ~2–3 days)

**1a. Parse and strip the header block.** A `sop_header.py` module that:
- extracts the 9 metadata fields into a structured object,
- splits the article body at `(YOUR CONTENT STARTS HERE)`,
- splits the references at `FOOTNOTES / LINKS` or a `References` heading,
- **passes only the body to the scoring engine** (fixes §4),
- returns per-field `CheckItem`s for anything missing.

**1b. Enforce word count.** Add `word_min` / `word_max` to `EvaluationRequest`
(default 300/350 for short-form). A check plus an issue when out of range — measured
on the body only, which 1a now makes correct.

**1c. Structural checks.** Subheadings present (H2/H3), references section present
and non-empty, every reference a resolvable URL, no flat-text wall.

**1d. Show it in the sidebar.** A "SOP Compliance" panel above the score — a simple
pass/fail list. The `CheckItem` pattern and its UI already exist, so this is mostly
wiring.

> Why first: it is deterministic, needs no AI, no new infrastructure, and replaces
> the most tedious part of the editor's job. It is also what makes the score honest.

### Phase 2 — Editorial mandates (~2–3 days)

**2a. Nation-first check.** This needs care. I would implement it as a *flag for human
review*, never an automatic verdict: surface unverified claims and loaded framing
about national institutions for the editor to judge. Encoding "anti-national" as an
automatic score penalty risks suppressing legitimate, well-sourced critical
reporting — which the SOP itself demands be *evidence-based*. It belongs in the
integrity report, next to the existing unattributed-claim findings.

**2b. Fact-check worklist.** Turn `analyze_integrity` output into an editor-facing
checklist: every claim with a statistic, each with its nearby citation, each
tickable. This directly serves "manually click hyperlinked citations to verify."

**2c. AI/plagiarism gate.** Fields + validation as described in §6.

**2d. Add the SOP's named sources to the tier list.** A one-line fix with real effect:
*Indian Express*, *Firstpost* and *Google Scholar* are named in the SOP but absent from
`SOURCE_TIERS` (`constitution.py:120-131`), so citing them earns no credit today. While
there, consider matching on URL domain rather than substring — at present the bare word
"university" anywhere in the text scores a Tier 3 source.

### Phase 3 — The production loop (largest, ~1 week)

The genuinely new subsystem: assignment briefs, `assigned_at` / `due_at`, the 12–18h
and 10–12h windows, a state machine (`assigned → drafting → submitted → under_review
→ revising → approved`), GTG sign-off recorded against an evaluation, overdue
detection, and Slack/Teams notifications (the integration already exists at
`integrations/notify.py`).

Worth saying plainly: **this is a workflow tracker, and it is where Jalebi stops
being a grammar-adjacent tool and becomes the department's operating system.** It is
also the part most likely to fail on adoption rather than engineering — it only works
if the team actually uses it for assignments.

---

## 8. Suggested order

0. **Settle the §4 conflict** — decide whether the bullet penalty and the length
   reward apply to SOP short-form. This is a decision, not code, and everything
   downstream depends on it. Until it is settled, Jalebi and the SOP disagree about
   what "good" means.
1. **1a header parsing** — correctness fix; unblocks everything else
2. **1b word count** + **1c structure** — immediate daily value
3. **1d sidebar panel** — makes 1a–1c visible
4. **2c AI/plagiarism gate** — cheap, closes a zero-tolerance SOP item
5. **2b fact-check worklist** — reuses the existing integrity analyzer
6. **2a nation-first** — needs the most design care; do it deliberately
7. **Phase 3** — after 1–2 are proven in real use

**Not recommended yet:** formatting checks (§6), and any homegrown AI-detection.

---

## 9. Open questions

These are product calls, not technical ones. I can implement any answer, but I should
not pick them silently.

**1. Does the Constitution or the SOP win on bullets and length?** (§4.) My
recommendation is to scope both rules by content type, but this changes what Jalebi
tells writers "good" means, so it needs an owner's decision.

**2. How does the 300–350 word limit apply?** The SOP specifies it for "standard
short-form analytical articles," but Jalebi supports 17 content types. Cleanest answer
is **per-assignment with a per-type default** — but that presumes assignments exist,
which is Phase 3.

**3. Is the SOP header block mandatory for every content type, or only short-form?**
This determines whether a missing header is a hard failure or a warning.

**4. Who fills in the AI/plagiarism percentages?** The SOP assigns the checks to the
editor. If Jalebi gates sign-off on those fields, the editor must enter them — worth
confirming that matches how the team actually works.
