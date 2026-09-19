# Jalebi — Hardening Plan & Task Calendar

**Created:** 19 September 2026
**Goal:** take Jalebi from "works on my machine for TIES" to "safely deployable and
maintainable", then to "usable by anyone".

Every item below was **verified against the running code**, not carried over from an
earlier document. Where I found something new while checking, it is marked 🆕.

---

## Scope decisions (made, not deferred)

I was asked not to hand decisions back, so these are settled:

| Decision | Choice | Why |
|---|---|---|
| Deployment target first | **Harden before generalise** | Shipping a multi-tenant product on an unhardened base multiplies the blast radius |
| npm vulnerabilities | **Upgrade tooling, don't panic** | Verified: all 21 are build-time only; runtime deps are React + React-DOM alone |
| Sentence splitting | **Extract one shared module** | Found 4 implementations, 2 still buggy (🆕 below) |
| Analytics scans | **SQL aggregation** | Already proven in `admin.py:149` |
| Rewrite endpoint provider | **Route through the allow-list** | Config that doesn't constrain is a lie |
| TIES generalisation | **Phase 4, after hardening** | Correctness first |

---

## 🆕 New findings from this pass

**1. Two more broken sentence splitters.** I predicted a third copy existed; there are two.

- `app/analysis/analyzers.py:14` — `(?<=[.!?])\s+`
- `app/pipeline/text_features.py:62` — same pattern

Measured impact:

```
Input:  "Dr. Rao said exports rose 12.7% in FY24. The trend held."
Split:  ['Dr.', 'Rao said exports rose 12.7% in FY24.', 'The trend held.']
Integrity claim recorded: "Rao said exports rose 12.7% in FY24."
```

The attribution (`Dr.`) is severed from the claim, so **a properly attributed statement
can be analysed as though it had no source**. This is the same defect class already fixed
twice in `rules.py` and `factcheck.py` — fixing it in one place is now a correctness
requirement, not tidying.

**2. The npm audit is less alarming than the count suggests.** All 21 vulnerabilities
(5 critical, 10 high) are in build tooling — `wxt`, `vitest`, `vite`, `web-ext-run`,
`firefox-profile`, `tar`, `shell-quote`. Verified: `package.json` runtime dependencies are
**only `react` and `react-dom`**, and no vulnerable package appears in the shipped bundle.
Real risk is to a developer machine or CI, not to a user who installs the extension.

---

## 🆕 Revision: making the no-key path genuinely good

Jalebi must be excellent **without an API key** — that is the zero-infrastructure
promise, it is how every test runs, and it is a real differentiator against tools that
are useless offline. Measured on the running system:

```
Overall determinism with NO key: 64% of the score
  breaking_news 72%   investigative 69%   analysis 60%   opinion 58%
```

The remaining 36% is not evenly spread — it collapses into three dimensions whose rule
component is weak or absent:

| Dimension | Weight | alpha (rule share) | Rule behaviour with no key |
|---|---|---|---|
| `insight` | 0.20 | **0.15** | **Returns a flat 60.0**, +8 if the text contains one of nine phrases like "surprisingly" |
| `depth` | 0.10 | 0.60 | Length + mechanism-word counting |
| `narrative` | 0.15 | 0.60 | Paragraph/transition heuristics |

Measured consequence — a well-sourced analytical piece against vacuous filler:

```
STRONG  overall=70   insight=60  depth=66  narrative=70
WEAK    overall=65   insight=60  depth=55  narrative=55
```

**`insight` scores 60 for both.** The rule rewards *claiming* insight ("surprisingly")
rather than exhibiting it, so on the no-key path a fifth of the score is a constant. A
5-point overall gap between excellent and vacuous is not a usable editorial signal.

**Day 3 is therefore re-scoped** to strengthen the deterministic engine, which is worth
more than the performance work it displaces. The displaced items move to Day 4.

## The calendar

Five days of focused work, sequenced so each day ends green and shippable.

### Day 1 — Correctness (the bugs that produce wrong answers)

| # | Task | File(s) | Why it matters |
|---|---|---|---|
| 1.1 | Extract `app/text/sentences.py`; repoint all 4 call sites | `analyzers.py`, `text_features.py`, `rules.py`, `factcheck.py` | 🆕 Attribution severed from claims |
| 1.2 | Qdrant point ids from `hashlib`, not `hash()` | `knowledge/store.py:85` | `hash()` is per-process randomised → upserts never update, duplicates accumulate |
| 1.3 | Stop sending the Anthropic key to OpenAI | `knowledge/embeddings.py:36` | Cross-provider secret transmission |
| 1.4 | Remove the invalid default model id | `config.py:55`, `registry.py:59` | `claude-opus-4-8` fails at call time, not startup |

**Exit:** all tests green, new tests pin each fix against the old behaviour.

### Day 2 — Resilience (the failures that take the service down)

| # | Task | File(s) | Why it matters |
|---|---|---|---|
| 2.1 | Timeouts + retries on all three LLM clients | `llm/client.py`, `openai_client.py`, `gemini_client.py` | A stalled provider holds a request **and its DB session** ~20 min |
| 2.2 | Bound concurrent fan-out | `hybrid_evaluator.py` | Multiplies 2.1 |
| 2.3 | Trust `X-Forwarded-For` only from configured proxies | `middleware.py:17` | Rate limiting is the only abuse control on the expensive path, and is bypassable per request |
| 2.4 | Stop leaking provider/DB errors to clients | `rewrite.py:97`, `health.py:39` | SQLAlchemy errors carry the DSN **with credentials**; `/health/ready` is unauthenticated |
| 2.5 | Route `/api/rewrite` through the provider allow-list | `rewrite.py:76` | `JALEBI_ALLOWED_PROVIDERS` currently does not constrain it |

**Exit:** a hung provider cannot exhaust the worker pool; no secret can leave in an error.

### Day 3 — Make the no-key engine genuinely good

| # | Task | File(s) | Why it matters |
|---|---|---|---|
| 3.1 | Real `insight` rules: evidence→conclusion structure, causal reasoning, specificity, originality vs. restatement | `scoring/rules.py:336` | Currently a constant 60; a fifth of the no-key score carries no information |
| 3.2 | Strengthen `depth`: mechanism/causal-chain analysis, not word counting | `scoring/rules.py` | Rewards length over reasoning |
| 3.3 | Strengthen `narrative`: openings, transitions, earned endings | `scoring/rules.py` | Thin heuristics |
| 3.4 | Grammar false positives (`a/an`, newline-eating) | `grammar/heuristic.py:109` | Verified wrong on "a university", "an hour", "a European", "an FBI"; the space-before-punctuation fix **deletes paragraph breaks** |
| 3.5 | Raise alphas to match the stronger rules; re-verify determinism | `scoring/constitution.py` | The rule share should rise because the rules got better, never by fiat |

**Exit:** a clear, defensible score gap between strong and weak writing with no key, and
overall determinism materially above 64%.

### Day 4 — Performance, data integrity, frontend

| # | Task | File(s) | Why it matters |
|---|---|---|---|
| 4.1 | SQL aggregation for analytics | `services/analytics.py:22` | `SELECT *` pulls every 10–50 kB result blob into Python per dashboard load |
| 4.2 | Same for the documents tracker | `services/documents.py:34` | Three full-table scans per request |
| 4.3 | Startup failures logged, not `print`-and-swallow | `main.py:66` | A failed reindex silently yields an empty vector store |
| 4.4 | Fix `ReviewCanvas` replace-by-string | `ReviewCanvas.tsx:156` | Replaces the **first** match, not the marked one; `$&`/`$1` in model output corrupts text |
| 4.5 | Clean up timers on unmount | `ReviewCanvas.tsx:119,173` | setState after unmount |
| 4.6 | Destroy inline checkers for detached fields | `inline.content.ts` | Unbounded leak on SPAs — one per field ever focused |
| 4.7 | Upgrade build tooling | `package.json` | 21 advisories; build-time only but CI/dev exposure is real |

**Exit:** dashboard queries bounded; extension typecheck, tests and build green.

### Day 5 — Documentation & release readiness

| # | Task | Output |
|---|---|---|
| 5.1 | Rewrite `README.md` | Accurate quick start; remove claims the code no longer supports |
| 5.2 | Update `docs/ARCHITECTURE.md` | Reflect HybridEvaluator-only, deleted modules, workflow + SOP layers |
| 5.3 | Write `docs/DEPLOYMENT.md` | The production config the startup guard demands |
| 5.4 | Write `docs/CONFIGURATION.md` | All env vars, defaults, and what each affects |
| 5.5 | Refresh `AUDIT.md` / `BUG_REPORT.md` | Mark resolved items; keep the record honest |

---

## Explicitly out of scope for this pass

- **Multi-tenancy and TIES generalisation** — planned in `PRODUCT.md`, ~7 weeks, and
  should not start until the base is sound.
- **AI detection** — evidence in `PRODUCT.md` says don't build it.
- **Google Docs API formatting checks** — high plumbing, low value.

## Outcome

All five days complete.

| | Start | End |
|---|---|---|
| Backend tests | 249 | **349** |
| Extension tests | 56 | **60** |
| Determinism with no API key | 64% | **72%** |
| Strong-vs-weak score gap | 5 points | **14 points** |
| Extension bundle | 326 kB | **307 kB** |

Things found while doing the work that were not in the original plan:

- **Two more broken sentence splitters** (predicted one; found two). Both severed
  attributions from their claims, so an attributed statement could be analysed as
  unattributed. Now a single shared module.
- **`insight` was a constant.** It returned 60.0 for every input, so a fifth of the
  no-key score carried no information and vacuous filler scored the same as genuine
  analysis. Replaced with structural reasoning analysis.
- **The grammar checker corrected correct English** — "a university", "an hour", "a
  European", "an FBI agent" — because it matched spelling rather than sound. The
  space-before-punctuation fix also deleted paragraph breaks.
- **`pass_rate` divided the fetched rows by the full table count**, which would have
  silently understated the figure once history exceeded the query window.
- **Fixes were applied by string pattern**, so `String.replace` rewrote the first match
  rather than the highlighted one and interpreted `$&`/`$1` in model output.
- **`JALEBI_PIPELINE` was dead config**, read only to be echoed in the health response.
  Removed rather than documented.

## Acceptance criteria for the whole pass

1. Backend suite green and larger than 249; extension green and larger than 56.
2. Every fix has a test that **fails against the pre-fix code** — the standard used
   throughout this project.
3. No behaviour change for TIES: the existing scoring must be reproducible.
4. Documentation describes what the code does, not what it was once intended to do.
