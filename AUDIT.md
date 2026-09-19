# Jalebi — Code Audit

> **Status: historical.** This is the original audit, kept as the record of what was
> found. Everything in the Blockers and High sections has since been fixed, along with
> most of the Medium tier — see [PLAN.md](PLAN.md) for the work and the commit history
> for each fix. The test suite has gone from 39 (7 failing) to 349 backend and 60
> extension tests. Findings below are **not** a description of the current codebase.

Full read of ~6,700 lines of Python and ~3,800 lines of TypeScript, plus a verified
build/test run of both apps. Findings below are grouped by severity and each one
names the file and line so it can be actioned directly.

Verified by execution (not just reading):

| Check | Result |
|---|---|
| Backend `pytest` | **7 failed**, 39 passed |
| Extension `tsc --noEmit` | clean |
| Extension `vitest` | 7 passed |
| Extension `wxt build` | succeeds (313 kB) |
| `npm audit` | 21 vulnerabilities (5 critical, 10 high) |

---

## Blockers

### B1. Test suite fails on Python 3.12+ — CI is not green
`tests/test_evaluation.py:43`, `tests/test_llm_evaluator.py:52`

Both use `asyncio.get_event_loop().run_until_complete(...)`. Since Python 3.12 this no
longer creates a loop implicitly and raises `RuntimeError: There is no current event
loop`. 7 tests fail. CI pins `python-version: "3.12"`, so **CI is failing on `main`
as committed.**

Fix: `asyncio.run(ev.evaluate(req))` in both helpers.

### B2. Rate limiter 500s on every request after 10k keys — *reproduced*
`app/middleware.py:33,51`

`self._hits` is a `defaultdict`, but the cleanup at line 51 rebinds it to a **plain
dict** comprehension. The next request with an unseen key hits `self._hits[key]` at
line 44 and raises `KeyError`, inside middleware, before `call_next` — a 500 for
every new client, permanently, until the worker restarts.

I reproduced this exactly:

```
type after cleanup: dict
CONFIRMED KeyError -> 'brand-new-ip:100' = HTTP 500 for every new client
```

It is remotely triggerable: `_client_ip` (`middleware.py:17`) trusts
`X-Forwarded-For` unconditionally, so anyone can rotate the header to mint 10k keys
and take the API down.

Fix: `self._hits = defaultdict(lambda: (0, 0), {k: v for k, v in self._hits.items() if v[0] >= window})`
— or use `.get(key, (0, 0))` at line 44 and drop the `defaultdict` dependency entirely.

### B3. Auth fails open on defaults
`app/config.py:58,72`

`jwt_secret` defaults to the literal `"dev-insecure-change-me"`, which is public in
this repo. `allow_dev_login` defaults to `True`, `signup_secret` to `""`, and
`_email_allowed` (`auth/service.py:22`) treats empty allow-lists as **allow-any**.
Nothing validates any of this at startup.

With stock defaults: `POST /api/auth/dev-login {"email": "founder@ties.org"}` creates
an account unauthenticated, and if that address is in `JALEBI_ADMIN_EMAILS` it is
auto-promoted to admin (`auth/service.py:56`). Anyone can also forge
`{"sub":"1","role":"admin"}` against the known secret.

Fix: hard-fail startup when `environment == "production"` and the secret is the
default or under 32 bytes, or dev-login is on without a signup secret. Fail closed.

### B4. OAuth callback — no `state` check, token injected raw into HTML
`app/api/routes/auth.py:56,74-83`

Three issues in one handler:
- `google_login` generates `state = secrets.token_urlsafe(16)` and returns it, but
  `google_callback` never accepts or verifies a `state` parameter. The CSRF defense is
  generated and thrown away → login CSRF / session fixation.
- `{token!r}` emits a **Python** repr into a **JavaScript** string context — different
  escaping grammars, so this is context confusion regardless of input trust.
  `user.email` is interpolated unescaped.
- `postMessage({...}, '*')` broadcasts the bearer JWT to **any** origin that opened the
  window.

Fix: verify `state` server-side; `html.escape()` the email; `json.dumps()` the token;
replace `'*'` with the exact expected origin.

### B5. Inline checker corrupts user text on race
`lib/inline/checker.ts:64-82`

`run()` awaits the backend with **no request-generation token** — the only guard is
`this.destroyed`. Debounce narrows but does not close the window: request A fires,
the user types, request B fires, A resolves last and overwrites `this.text` while
`this.issues` holds B's offsets. Every derived value then points at the wrong span.

The consequence is not cosmetic: `apply` (`checker.ts:229`) calls
`replaceRange(issue.offset, issue.length, …)` using offsets computed against a
*different* string — **it will corrupt text in a live editor on any site.**

Fix: `const my = ++this.seq` before the await; `if (this.destroyed || my !== this.seq) return;`
after. Re-verify `field.getText() === this.text` before applying a fix.

### B6. `<all_urls>` content script ships keystrokes to a user-settable host
`wxt.config.ts:29`, `entrypoints/inline.content.ts:11`, `lib/inline/editable.ts:5`

The inline checker injects into **every page on the internet** — banking, healthcare,
internal admin panels, password resets — and POSTs field contents to
`getBackendUrl()`, which the user can point at **any origin** (`Settings.tsx:45`,
backed by `optional_host_permissions: ['https://*/*', 'http://*/*']`).

The comment at `editable.ts:13` says it requires "a reasonable size to avoid tiny
one-line search boxes." **The code does no such check** — a comment describing a
mitigation that does not exist.

This will fail Chrome Web Store review under the limited-use policy, and it is a
genuine privacy defect either way.

Fix: implement the size filter the comment promises; skip fields in any form
containing `input[type=password]` and any `autocomplete` of `cc-*`,
`one-time-code`, `current-password`, `new-password`; move `<all_urls>` to opt-in
per-site; drop `http://` from the optional origins.

---

## High

### H1. The rubric system and 4 of 5 evaluators are unreachable dead code
`app/llm/registry.py:154`

`build_evaluator` routes **every** provider, including `mock`, to `HybridEvaluator`,
which sources weights from `app/scoring/constitution.py` and never touches
`app/rubrics/`. Dead as a result: `orchestrator.py`, `llm_evaluator.py`,
`multi_agent.py`, `claude_evaluator.py`, `mock_reviewer.py` (all 15 reviewers),
`aggregate.py`, `prompt.py`, and **all 17 rubrics**.

Two user-visible consequences:
- `PUT /api/admin/rubrics/{content_type}` persists, returns updated weights, and
  reloads at startup — **and changes nothing about how anything is scored.** Admins
  tune weights and see zero effect.
- `JALEBI_PIPELINE=multi` is documented in the README and read only by `health.py:21`.
  The multi-agent mode **cannot be enabled at all.**

Fix: decide which engine is authoritative. Either point `HybridEvaluator` at
`app.rubrics.get_rubric()`, or delete the dead modules and repoint the admin UI at
`constitution.WEIGHTS_BY_TYPE`. Until then the rubric endpoint should return 501
rather than silently no-op.

### H2. "Ready to Publish" returned for documents with critical issues
`app/scoring/engine.py:93` vs `96-113`

`readiness` is computed at line 93 from score bands **only** — the `critical` list is
not assembled until line 96, *after* the decision. A piece scoring ≥85 with
model-reported critical issues is still labelled `Ready to Publish` with
`publication_ready=True`. Hard caps constrain this, but AI-detected critical issues
trigger no cap, so they never influence readiness.

The correct policy already exists in `aggregate.py:26` (`judge_readiness` checks
`has_critical`) — but that is on the dead path from H1.

Fix: move the readiness computation below the `critical` assembly and gate on
`any(i.priority == Priority.critical for i in critical)`.

### H3. `/api/check` stalls the event loop ~5s on large input
`app/grammar/heuristic.py:176-186`, via `async def check` in `grammar/service.py:18`

`contained()` is O(n²) over issues and runs **synchronously inside an async handler**,
so it blocks the whole worker — every concurrent request, not just this one. Measured
on the real code: 61,200 chars → 6,600 issues → **4,907 ms**. `/api/check` accepts up
to 60,000 chars and is the *real-time inline* endpoint, i.e. the hot path. Cost is
quadratic.

Fix: make `contained()` a linear sort-and-sweep, and offload regardless with
`await anyio.to_thread.run_sync(heuristic.check, text)`. Use a smaller cap for
`/api/check` than the 60k document limit.

### H4. Google Docs extraction — the core feature — has a broken fallback path
`lib/doc.ts:26-35`, `entrypoints/content.ts:39-48`

`fetchDocText` is imported by both the content script and the background worker. In
the worker there is no `docs.google.com` context, so the export fetch is cross-origin
and the **302 to `accounts.google.com`** (multi-account profiles — the common case in
a newsroom) is not in `host_permissions` and fails opaquely. `res.ok` then passes on a
200 HTML login page, caught only by a crude body sniff.

Separately, `content.ts:39-48` has two disjoint branches: if `resp.ok === true` but
`resp.text === ''`, neither runs and the fallback is skipped — the user is told
"The document appears to be empty" when the fallback would have worked.

Fix: do the export fetch only in the content script where it is genuinely
same-origin; restructure to a single fallback condition; check `res.redirected` and
`content-type` rather than sniffing the body.

### H5. No timeouts on any LLM client
`app/llm/client.py:66`, `openai_client.py:63`, `gemini_client.py:27`

None of the three pass a timeout or configure `max_retries`; they inherit the SDK
defaults (~600 s). `HybridEvaluator._call_with_repair` then loops `max_attempts=2`, so
a stalled provider can hold a request *and its DB session* for ~20 minutes.
`MultiAgentEvaluator` fans out concurrently, multiplying it.

Notably the rest of the codebase gets this right: `auth/oauth.py:34` (15 s),
`grammar/languagetool.py:34` (8 s), `integrations/notify.py:15` (8 s).

Fix: `timeout=60.0, max_retries=2` on each client; bound the `gather` with
`asyncio.wait_for`.

### H6. Migration adds four NOT NULL columns with no server default
`migrations/versions/848eaac5682b_document_sop_fields.py:22-25`

The models declare Python-side `default=`, which SQLAlchemy applies on INSERT only —
it emits no DDL. On Postgres, `ADD COLUMN ... NOT NULL` without a default against a
table with rows **raises**. The Dockerfile runs `alembic upgrade head` on every
container start, so this is a hard deploy failure on any environment with existing
`documents` rows.

It passes today only because dev uses SQLite with `render_as_batch=True`, which
rebuilds the table and masks it until the first real Postgres deploy.

Fix: `server_default=''` on the three string columns, `server_default='draft'` on
`status`.

### H7. Inline checkers are never destroyed — unbounded SPA leak
`entrypoints/inline.content.ts:24-51`

Only `focusin` is handled. When a focused field is removed from the DOM (SPA route
change, modal close, Gmail compose closed), nothing calls `detach()`. The checker
keeps its `window` scroll/resize listeners, a `document` `mousemove` **capture**
listener, a `storage.onChanged` listener, and three orphaned `document.body` children
— one full leaked checker **per field the user ever focused**, each doing rAF
repositioning on every scroll event. On Gmail/Notion/LinkedIn (the stated targets)
this accumulates all session.

Fix: detach when `currentEl && !currentEl.isConnected`, and on `pagehide`.

---

## Medium

- **CORS defaults to `*`** (`config.py:125`). `allow_credentials=False` is correct, but
  this API authenticates by `Authorization` header with `allow_headers=["*"]`, which
  the credentials flag does not cover. Any origin can drive the full admin API with a
  leaked token.
- **`X-Forwarded-For` trusted unconditionally** (`middleware.py:17`). Rate limiting —
  the only abuse control on the expensive `/api/evaluate` path — is bypassable per
  request, and it is the trigger for B2. Uvicorn is started without `--proxy-headers`.
- **Provider errors echoed to clients** (`rewrite.py:96`, `health.py:39`). SDK
  exceptions embed URLs, org ids, sometimes truncated keys; SQLAlchemy errors commonly
  include **the DSN with credentials**. `/api/health/ready` is unauthenticated.
- **Stored XSS in the dashboard** (`dashboard/views.py:120`). `<a href="${d.url}">${d.title}</a>`
  is built via `innerHTML` from `doc_url`/`title` — unvalidated free text from
  `/api/evaluate`, which is unauthenticated by default. A writer plants
  `javascript:` or `"><script>`; it fires in an **admin's** browser. Writer → admin escalation.
- **Rubric override accepts weights that zero or invert scores** (`admin.py:88`).
  Only keys are validated. All-zero → `or 1.0` → every weight 0 → every document
  scores 0. Negatives flip the sign. Setting `accuracy: 0.90` silently stores
  `0.5233` after renormalisation and reports the rescaled number back.
- **Quantisation shifts scores with no model running** (`engine.py:71`). In the
  rules-only path `ai_s = _q5(rule_s)` — the rule score is quantised and blended into
  itself, drifting ±2 per dimension in the mode the docstring calls "rules-only".
- **Full-table scans per request** (`services/analytics.py:22`, `documents.py:18`).
  `select(Evaluation)` with no pagination pulls the whole `result` JSON blob
  (10–50 kB/row) into Python on every dashboard load. `admin.py:149` already does this
  correctly with SQL aggregation.
- **`EvaluationMeta` schema drift** (`lib/types.ts:52` vs `evaluation.py:88`). Every
  backend field except `content_type` has a default; TS declares all 7 **required**.
  `Scorecard.tsx:31-36` reads them unguarded → `undefined` in the UI. Also
  `AuthUser` is missing `department`; `classify` and `providers` return untyped
  `dict` with no `response_model`.
- **`detail` rendered blind** (`lib/api.ts:74`). FastAPI 422 returns `detail` as an
  **array of objects**; React throws "Objects are not valid as a React child" →
  white-screen on any validation error. No timeout or `AbortController` either, so a
  hung backend leaves the panel stuck in `evaluating` forever.
- **`ReviewCanvas` replaces by string, not index** (`ReviewCanvas.tsx:156,166`).
  `w.replace(m.quote, …)` hits the **first** occurrence, which may not be the marked
  one, and `$&`/`$1` in model output is interpreted as a replacement pattern — a
  model emitting `"$1,000"` corrupts the text.
- **Grammar false positives on correct English** (`heuristic.py:109`). Verified:
  `"a university"` → "an university", `"an hour"` → "a hour", `"a European"` →
  "an European", `"an FBI"` → "a FBI". The rule matches spelling, not sound. The
  space-before-punctuation rule matches across newlines, so applying the fix **deletes
  paragraph breaks**.
- **Qdrant ids use Python `hash()`** (`knowledge/store.py:85`), which is randomized
  per process. Point ids differ across restarts, so `upsert` never updates — it
  accumulates duplicates.
- **Anthropic key sent to OpenAI** (`knowledge/embeddings.py:36`).
  `OpenAI(api_key=settings.anthropic_api_key or None)` — with
  `JALEBI_EMBEDDING=openai` and an Anthropic key set, an `sk-ant-...` key is
  transmitted to `api.openai.com`. Failure is swallowed, so it degrades silently.
- **`claude-opus-4-8` is not a valid model id** (`config.py:55`, `registry.py`). An
  `anthropic` request with no `JALEBI_MODEL` fails at call time, not startup.
- **`vitest` runs in `environment: 'node'`** (`vitest.config.ts:11`), so no DOM test
  can run. Every risky module in this audit — `rects.ts`, `editable.ts`, `checker.ts`,
  `overlay.ts` — is **completely untested**; the 2 test files cover pure string
  helpers. No `exclude` for `node_modules` either.
- **21 npm vulnerabilities** (5 critical, 10 high). WXT 0.19 is well behind current.

---

## What is genuinely well built

Worth stating plainly, because it is not a bad codebase:

- **Role-based access control is complete and correct.** All 24 routes mapped: every
  `/api/admin/*` has `Depends(admin_only)`; `require_role` reads `user.role` from a
  freshly-fetched DB row rather than the JWT claim, so demotion takes effect
  immediately. No missing check found.
- **Zero SQL injection.** Every query uses bound Core/ORM constructs; the only raw SQL
  is a constant `text("SELECT 1")`.
- **JWT handling is correct** — explicit `algorithms=["HS256"]`, so no `alg:none` or
  algorithm confusion. `exp` set and verified.
- **Zero broken imports** across 73 modules (checked by AST).
- **Migrations match models** on every column and index across all 6 tables; the
  revision chain is linear. H6 is the only drift.
- **The LLM JSON-repair path is solid** — catches parse failures, feeds the error back
  for one repair attempt, degrades to a rules-only report instead of erroring.
  `ai_prompt.parse` clamps scores and filters placeholder echoes.
- **Edge inputs don't crash.** Empty, single-sentence, unicode, and no-citation inputs
  were exercised against the real regexes and math: division guards hold, CJK titles
  are safe, all rubric weight vectors sum to exactly 1.0.
- TypeScript is `strict: true` with almost no `any` and no `dangerouslySetInnerHTML`;
  all model-returned content reaches the DOM via `textContent` or JSX text children.

The weaknesses cluster in **defaults that fail open** and in **a scoring engine that
was swapped out without removing what it replaced** — not in the access-control logic.

---

## Suggested order

1. **B1** — one-line test fix, gets CI green so everything after is verifiable.
2. **B2** — one-line limiter fix; active remotely-triggerable 500s.
3. **B3, B4** — auth defaults and the OAuth callback.
4. **B5, B6** — the two extension issues that affect users' text and privacy.
5. **H1** — decide the engine story; it invalidates the admin rubric feature as shipped.
6. **H2, H3** — wrong results and the event-loop stall.
7. **H6** — before the next Postgres deploy.
8. Medium tier, then dependency upgrades.
