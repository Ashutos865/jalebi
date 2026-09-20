# Jalebi — Full Feature Audit

**Date:** 20 September 2026
**Method:** every feature exercised against the running server, not read from source.
38 API endpoints enumerated from the live OpenAPI spec; 24 probed with real payloads;
each result inspected for *usefulness*, not just HTTP 200.

> **Why this matters:** all 24 endpoints returned 200. If the audit had stopped at
> status codes it would have reported a clean bill of health. Every defect below sits
> behind a successful response.

---

## Verdict in one table

| Feature | State | Evidence |
|---|---|---|
| Scoring engine (7 dimensions) | **Strong** | 81/100 on a good article, 45–60 on capped ones |
| Hard caps | **Strong** | 3 of 4 fire correctly; 4th is advisory by design |
| SOP compliance (TIES) | **Strong** | 10 checks, all 7 header fields parsed |
| Fact-check worklist | **Broken ranking** | Tier 1 and a tweet both rank `high` |
| Integrity analyzer | **Working, shallow** | Absolute unsourced prediction = only `medium` |
| Nation-First review | **Strong** | Catches hearsay-laundered disparagement |
| Auto-classify | **Working** | 0.95 on news, 0.67 on opinion/analysis |
| Grammar check | **Weak** | **caught 2 of 10** faults |
| a/an rule | **Broken** | fires on **0 of 4** of its own cases |
| Rewrite / paraphrase | **Needs provider** | returns `engine: unavailable` on mock |
| AI judgment layer | **Now working** | first live call ever: 8.1s, real judgment |
| Error handling on provider failure | **Broken** | 402 → HTTP 500, not rules-only |
| Analytics | **Working** | 11 evaluations, trend, top issues |
| Knowledge base / RAG | **Working** | 4 relevant hits for "attribution" |
| Workflow + SLA | **Strong** | state machine, optimistic locking |
| Admin (users, rubrics, logs) | **Working** | all guarded, all return data |
| Auth guards | **Correct** | admin/tracker 401; analysis public by design |

---

## Critical — fix these first

### C1. A provider error takes down scoring entirely

**The single most important finding.** `_call_with_repair` catches only
`asyncio.TimeoutError`. Every other provider failure propagates and becomes an HTTP 500.

Reproduced: with OpenRouter configured but the account out of credit, `POST /api/evaluate`
returned **HTTP 500**. The raw exception was a 402 from the provider.

```
openai.APIStatusError: Error code: 402 - This request requires more credits...
```

The docstring directly above the handler promises otherwise:

> *"Exceeding it degrades to rules-only — the same graceful path as an unparseable
> reply — rather than failing the evaluation."*

That promise holds for timeouts and malformed JSON, and fails for 401 (bad key),
402 (no credit), 429 (rate limit) and 5xx (provider outage) — the four most likely
failures in production.

**Impact:** ~72% of the score is deterministic and needs no AI at all. A billing
hiccup should cost you the remaining 28%, not the whole feature.

**Fix:** catch `Exception` around the provider call and return the same
`AIReport(summary="(AI judgment unavailable; …)")` the retry-exhausted path returns.

---

### C2. `openai` is not installed, so five providers cannot work

`requirements.txt` line 16:

```python
# openai>=1.40   # GPT + all OpenAI-compatible: Ollama/OpenRouter/Groq/Together/DeepSeek/…
```

Commented out. Configuring any OpenAI-compatible provider crashes at first call with
`ModuleNotFoundError: No module named 'openai'` — after the key is accepted and the
request is built, so it looks like a code bug rather than a missing dependency.

Affects **OpenRouter, Groq, Together, DeepSeek, Mistral, xAI and Ollama** — every
provider except Anthropic and Gemini.

**Fix:** uncomment it, or make the error message name the missing package.
*(Installed during this audit to complete testing.)*

---

### C3. Fact-check ranking ignores source quality for unlinked figures

The worklist exists to put the riskiest claims first. For any claim with a number and
no hyperlink it does not.

Measured:

| Claim | Tier | Risk |
|---|---|---|
| "…according to Ministry of Commerce data." | 1 | **high** |
| "…Reuters reported." | 2 | **high** |
| "…a Twitter post claimed." | 6 | **high** |
| "Exports rose 12.7% in FY24." (no source) | none | **high** |
| "…(https://commerce.gov.in), per Ministry data." | 1 | medium |

A Supreme Court judgment, Reuters, a tweet and nothing at all are ranked **identically**.
Only a hyperlink changes anything.

Cause — `app/analysis/factcheck.py:144`:

```python
elif has_number and citation is None:
    risk, reason = RISK_HIGH, "Statistic with no linked source…"
```

`citation` means a URL specifically, and this branch runs before any tier check.

> This is the same defect fixed earlier this week on the neighbouring branch (tier was
> ignored for claims *without* figures). That fix generalised the rule one branch too
> few.

**Fix:** consult `tier` inside this branch — a named tier 1–3 source without a link is
medium, not high.

---

## High — features that under-deliver

### H1. Grammar catches 2 of 10 faults

Ten ordinary errors put through `POST /api/check`:

| Fault | Example | Caught |
|---|---|---|
| Repeated word | "said that that the report" | **yes** |
| Space before punctuation | "This is wrong , clearly ." | **yes** |
| Subject–verb | "The ministry **have** announced" | no |
| their/there | "**Their** going to the office" | no |
| its/it's | "**Its** going to rain" | no |
| Misspelling | "unique **oppurtunity**" | no |
| a/an | "a **MBA**", "an **university**" | no |
| Wrong past tense | "exports **rised** 12%" | no |
| Run-on sentence | three clauses, no punctuation | no |
| Passive voice | "Mistakes were made" | no |

Engine reported: `heuristic`. That is the dependency-free fallback — roughly a dozen
mechanical rules (spacing, capitals, repeated words, a small typo list).

Real checking needs **LanguageTool**, already wired into `docker-compose.yml` and read
from `JALEBI_LANGUAGETOOL_URL`, which is unset.

```bash
docker run -d -p 8010:8010 erikvl87/languagetool:latest
# then in apps/backend/.env:
JALEBI_LANGUAGETOOL_URL=http://localhost:8010
```

**This is the gap between Jalebi and Grammarly/QuillBot** — not missing UI, a missing
grammar engine.

---

### H2. The a/an rule fires on none of its own examples

Not a limitation — a defect. The helpers are correct and never reached.

```
She has a MBA degree.      -> 0 issues
He went to an university.  -> 0 issues
It took a hour.            -> 0 issues
```

Yet the sound helpers work perfectly:

```
MBA         vowel_sound=True    hour        vowel_sound=True
university  consonant_sound=True  European  consonant_sound=True
```

Cause — the regexes match on **spelling**, so they never reach the sound test:

```python
re.finditer(r"\b(a)\s+([aeiouAEIOU]\w+)", text)                    # a + vowel LETTER
re.finditer(r"\b(an)\s+([b-df-hj-np-tv-zB-DF-HJ-NP-TV-Z]\w+)", text)  # an + consonant LETTER
```

"a MBA" is `a` + consonant-letter M, so neither pattern matches. The comment above the
rule says it exists precisely for sound-vs-spelling cases; those are the ones it misses.

**Fix:** match `\b(an?)\s+(\w+)` and let the sound helpers decide both directions.

---

### H3. Rewrite is unavailable without a paid provider

All five modes return `{"options": [], "engine": "unavailable"}` on `mock`. By design
(`rewrite.py:88`) — paraphrasing needs a real model. Worth stating plainly because the
UI offers the feature and the failure is silent.

Now works with OpenRouter configured.

---

### H4. Three working features have no UI anywhere

The extension calls **10 of 38** endpoints. These are fully functional and reachable
only by curl:

| Feature | Endpoint | What it produces |
|---|---|---|
| Fact-check worklist | `POST /api/factcheck` | claims ranked by risk, with tiers |
| Integrity analyzer | `POST /api/integrity` | unattributed claims, bias, absolutes |
| Nation-First review | `POST /api/nation-first` | unsourced disparagement queue |

The dashboard covers knowledge, rubrics, analytics and integrity *fields*, but has
**zero** references to factcheck or nation-first. Substantial, tested, invisible.

---

## Medium

### M1. Integrity severity is flat

"The economy will collapse entirely within months." — an absolute, unsourced prediction —
scores `integrity_score: 98` with one `medium` finding. The absolute ("entirely") and
the unfalsifiable prediction are not escalated.

### M2. Classifier confidence is low on analysis prose

News 0.95, opinion 0.67, analysis 0.67 — and one analysis sample scored 0.2 before
landing on `policy_analysis`. Usable as a suggestion, too weak to auto-apply silently.

### M3. `max_tokens: 16000` is hardcoded

`app/llm/openai_client.py:50`. No setting to tune it. This is what triggered the 402 —
the request asked for 16000 tokens when the balance afforded 2508. A smaller default,
or a `JALEBI_LLM_MAX_TOKENS` setting, makes Jalebi usable on modest budgets.

### M4. `pass_rate: 0.0` needs a definition

Average score 69.8 across 11 evaluations, but `pass_rate` is 0.0 — because none reached
"Ready to Publish". Correct but easy to misread as a bug.

### M5. Three modules have no tests

`auth.deps`, `grammar.languagetool`, `scoring.ai_prompt`. The last is the highest risk:
it parses model output, which is where malformed replies arrive.

### M6. `/api/providers` returns `available: []` after a reload

`uvicorn --reload` re-executes code but `load_dotenv()` does not override already-set
vars, so a reloaded process can score correctly while reporting no configured providers.
A full restart fixes it. Confusing rather than harmful.

---

## Low

- **L1.** Dependencies several majors behind: React 18→19, Vitest 2→5, WXT 0.19→0.21,
  TypeScript 5→7. **`npm audit`: 0 vulnerabilities**, so this is maintenance, not risk.
- **L2.** `allow_dev_login: True` and `cors_origins: ['*']` — correct for local
  development, must both change before any deployment.
- **L3.** `admin_emails: []` — the first user to log in becomes admin.
- **L4.** Google Docs is deliberately excluded from the inline grammar layer (canvas
  rendering, no editable target). Documented in code; users will still ask why.

---

## What is genuinely strong

Worth saying explicitly, because most of the system is in good shape.

- **Scoring engine** — 7 weighted dimensions, ~72% deterministic, identical every run.
- **Hard caps** — `unsupported_claim` → 50, `sensitive_allegation_unsourced` → 45,
  `opinion_as_fact` → 60. All verified firing.
- **SOP compliance** — all 7 header fields parsed correctly, 10 checks, word window
  enforced (flagged 122 words against 300–350), editor-only fields correctly excluded
  from author fault.
- **Nation-First** — correctly flags "Sources say the Indian Army has failed entirely"
  while leaving "According to the CAG report, the Ministry scheme failed" alone.
- **House style** — caught AI clichés, em dash, American spelling, absolutist phrasing
  and headline mismatch in one pass; writing score 33/100 on deliberately bad prose.
- **Workflow** — state machine, SLA clocks, optimistic locking, audit log.
- **Auth** — admin and tracker endpoints correctly 401 without a token.
- **Analytics** — trend, readiness breakdown, top issues, per-writer stats.
- **Tests** — 548 backend + 95 extension, every fix with a test that fails pre-fix.

---

## The AI layer now works

The first live provider call in this project's history was made during this audit.

```
provider : openrouter          model: mistralai/mistral-nemo
=== LIVE RESULT in 8.1s ===
score     : 77 | Needs Minor Revision
evaluator : openrouter
summary   : "…provides a useful data point on India's sovereign AI expansion
             but falls short in offering original insights…"
```

That summary is model-written; the mock never produces prose like it. Dimension scores
shifted too (Insight 77 vs 70, Sourcing 100 vs 80), confirming real judgment is blending
with the rules.

**On the key:** it was pasted into a chat transcript, so it should be treated as
compromised — revoke it at <https://openrouter.ai/keys> and put a fresh one in
`apps/backend/.env` (gitignored). The account has also nearly exhausted its balance,
which is what produced finding **C1**.

Sonnet 4.5 could not run — it requests 16000 tokens and the balance affords ~2508
(**M3**). `mistralai/mistral-nemo` works today at roughly $0.019 per million tokens.

---

## Recommended order

| # | Action | Effort | Why |
|---|---|---|---|
| 1 | Catch all provider errors, degrade to rules-only (**C1**) | ~1h | One billing failure currently kills scoring |
| 2 | Uncomment `openai` in requirements (**C2**) | 2 min | Five providers unusable without it |
| 3 | Rank fact-checks by tier when unlinked (**C3**) | ~1h | Worklist ordering is its whole purpose |
| 4 | Run LanguageTool (**H1**) | ~15 min | 2/10 → competitive grammar |
| 5 | Fix the a/an regex (**H2**) | ~30 min | Rule is dead as written |
| 6 | Make `max_tokens` configurable (**M3**) | ~20 min | Usable on small budgets |
| 7 | Surface factcheck / integrity / nation-first (**H4**) | ~1 day | Three features nobody can reach |
| 8 | Test `ai_prompt` parsing (**M5**) | ~2h | Parses untrusted model output |

Items 1–6 are roughly a day's work and address every critical and high finding.
