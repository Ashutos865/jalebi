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

### Day 3 — Performance & data integrity

| # | Task | File(s) | Why it matters |
|---|---|---|---|
| 3.1 | SQL aggregation for analytics | `services/analytics.py:22` | `SELECT *` pulls every 10–50 kB result blob into Python per dashboard load |
| 3.2 | Same for the documents tracker | `services/documents.py:34` | Three full-table scans per request |
| 3.3 | Startup failures logged, not `print`-and-swallow | `main.py:66` | A failed reindex silently yields an empty vector store |
| 3.4 | Grammar false positives (`a/an`, newline-eating) | `grammar/heuristic.py:109` | Verified wrong on "a university", "an hour", "a European", "an FBI"; the space-before-punctuation fix **deletes paragraph breaks** |

**Exit:** dashboard queries bounded; no user-visible wrong grammar suggestions.

### Day 4 — Frontend & dependencies

| # | Task | File(s) | Why it matters |
|---|---|---|---|
| 4.1 | Fix `ReviewCanvas` replace-by-string | `ReviewCanvas.tsx:156` | Replaces the **first** match, not the marked one; `$&`/`$1` in model output corrupts text |
| 4.2 | Clean up timers on unmount | `ReviewCanvas.tsx:119,173` | setState after unmount |
| 4.3 | Destroy inline checkers for detached fields | `inline.content.ts` | Unbounded leak on SPAs — one per field ever focused |
| 4.4 | Upgrade build tooling | `package.json` | 21 advisories; build-time only but CI/dev exposure is real |

**Exit:** extension typecheck, 56+ tests, build all green.

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

## Acceptance criteria for the whole pass

1. Backend suite green and larger than 249; extension green and larger than 56.
2. Every fix has a test that **fails against the pre-fix code** — the standard used
   throughout this project.
3. No behaviour change for TIES: the existing scoring must be reproducible.
4. Documentation describes what the code does, not what it was once intended to do.
