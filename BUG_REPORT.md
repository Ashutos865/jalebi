# Jalebi — Bug Report & Analysis

> **Status: historical.** This report describes the codebase as it was on
> 17 September 2026. All six blockers and every High finding have since been fixed,
> together with most Medium items; see [PLAN.md](PLAN.md) for the hardening work.
> Kept as the record of what was found and why it mattered — not as a description of
> the current system.

**Date:** 17 September 2026
**Scope:** full review of the `jalebi` repository (commit `c53b231`)
**Size reviewed:** ~6,700 lines of Python (backend), ~3,800 lines of TypeScript (Chrome extension)

This report has two parts:

- **Part 1 — For everyone.** Plain language. What the product does, what is broken,
  what it means in practice, and what to do first. No code.
- **Part 2 — For engineers.** Exact files, line numbers, root causes and code-level fixes.

---
---

# PART 1 — For a non-technical reader

## 1.1 What Jalebi is meant to do

Jalebi is an **automatic editor**. A writer finishes an article in Google Docs, clicks a
button, and Jalebi reads the piece and reports back like a senior editor would: what is
weak, why it matters, how to fix it, and whether the article is ready to publish.

It has two halves:

1. **The Chrome extension** — what the writer sees. A panel beside the document showing
   the score and the feedback. It also underlines grammar mistakes as you type, on any
   website, not just Google Docs.
2. **The server** — where the thinking happens. It runs the article through a scoring
   system and, optionally, an AI model (Claude, GPT, Gemini and others are supported).

## 1.2 The honest summary

**This is a well-built, ambitious project that is not ready to be used by real people yet.**

The structure is genuinely good. Someone competent designed this. The security model for
*who is allowed to do what* is correct and carefully done. There is no SQL injection
anywhere. The database design is sound.

But there are **six serious problems**, and three of them can cause real harm: one takes
the whole service offline, one lets an outsider become an administrator, and one can
silently corrupt text that a user is typing.

There is also a feature in the admin panel that **looks like it works and does nothing at all.**

## 1.3 Did it actually run?

I did not just read the code — I installed and ran it. This matters, because the project's
own documentation claims everything is finished and working.

| What I tested | Result |
|---|---|
| The server's own test suite | ❌ **7 tests fail** |
| The extension's type checking | ✅ Passes |
| The extension's tests | ✅ 7 pass |
| Building the extension | ✅ Works |
| Security scan of third-party code | ⚠️ **21 known vulnerabilities** (5 rated critical) |

The failing tests are important context. The project has an automated quality gate that is
supposed to catch mistakes before they reach users. **That gate is currently broken**, which
means nothing has been automatically checked for some time.

## 1.4 The six serious problems

### Problem 1 — The service can be taken offline by anyone, on purpose

**What happens:** The server has a protection that stops one person from flooding it with
requests. That protection has a flaw: after roughly 10,000 visitors, it breaks itself. From
that moment on, **every new visitor gets an error page**. It never recovers on its own —
someone has to restart the server.

Worse, an attacker does not have to wait for 10,000 real visitors. Because of a related
weakness, a single person can *pretend* to be 10,000 different visitors in a few seconds and
trigger it deliberately, whenever they like.

**I confirmed this by running the actual code.** It is not theoretical.

**What it means:** Jalebi goes down. Repeatedly. And anyone who discovers this can keep it down.

---

### Problem 2 — An outsider can make themselves an administrator

**What happens:** The system ships with insecure "convenience" settings switched **on** by
default, and nothing warns you or stops you when you go live:

- The secret key used to prove who you are is set to a default value that is **printed in
  this very code repository** — so it is public knowledge.
- A simplified "just type your email to log in" mode is **on by default**, with no password
  and no restriction on which email addresses are accepted.

**What it means:** With the default settings, a stranger can create an account and, if they
guess a founder's email address, be handed **full administrator access**. They can also forge
an admin pass entirely, because the secret is public.

This is the single most dangerous item in this report. It requires no skill to exploit.

---

### Problem 3 — The "Sign in with Google" flow leaks your access pass

**What happens:** Three separate flaws in one screen:

- A standard anti-fraud check is **created and then thrown away** — the code generates the
  security token and then never actually checks it. This lets an attacker trick you into
  logging into *their* account, so everything you then write goes to them.
- After signing in, the page **broadcasts your access pass to any website that asked for it**,
  rather than only to Jalebi.
- Your email address and pass are pasted into the page without proper sanitising, which is a
  classic route for injecting malicious code.

**What it means:** Account takeover. Someone else can end up holding your login.

---

### Problem 4 — The grammar checker can corrupt what you are typing

**What happens:** The "fix this" button works from a snapshot of your text. If you keep typing
while it is thinking, the snapshot and your real text drift apart. When you then click the
fix, it **edits the wrong position** — replacing text it was never meant to touch.

**What it means:** This is not a display glitch. It **changes the user's actual writing**, in
any text box on any website, and the user may not notice. For a writing tool, this is the
worst possible category of bug — it damages the very thing the user came to protect.

---

### Problem 5 — The extension reads every text box on every website

**What happens:** The grammar feature is installed on **the entire internet**, not just Google
Docs. Anything you type into any text field — online banking, medical forms, private internal
systems, password reset pages — is sent to a server for checking.

Two things make this worse:

- The destination server address **can be changed by the user to any address on the internet.**
- There is a **comment in the code** saying it avoids small/sensitive boxes. **The code does not
  do this.** The protection was described but never written.

**What it means:** This is a privacy problem regardless of intent, and Google will almost
certainly **reject the extension** from the Chrome Web Store for it. It needs fixing before
any public release.

---

### Problem 6 — The admin "scoring weights" panel does nothing

**What happens:** Administrators can open a settings panel and adjust how much each quality
factor counts toward the final score — for example, making "Accuracy" matter more than
"Writing style". The screen accepts the change, saves it, and shows the new values back.

**The scoring system never reads any of it.** At some point the scoring engine was replaced
with a better one, but the old one was left in place and the admin panel was never reconnected.
It now points at a part of the system that no longer decides anything.

**What it means:** This is arguably the most damaging problem for *trust*. Editors will tune the
settings, believe the scoring reflects their standards, and make publishing decisions on that
basis — **and every score will ignore their input entirely.** Nothing warns them. It fails silently.

The same is true of a "multi-agent" advanced mode that the documentation describes as finished:
**it cannot be switched on at all.**

## 1.5 Other things worth knowing

- **"Ready to Publish" is unreliable.** An article can be labelled ready to publish *even when
  the system itself has flagged critical problems in it*, because the verdict is decided before
  those problems are collected. An editor could publish something the tool already knew was unsafe.

- **The grammar checker corrects correct English.** I tested it. It changes "a university" to
  "an university", "an hour" to "a hour", "a European" to "an European", and "an FBI" to "a FBI" —
  **all four of those are wrong.** It also removes paragraph breaks when you accept certain fixes.

- **The service freezes on long documents.** I measured a **4.2 second total freeze** on a
  60,000-character document — and during that time the server cannot answer *anybody*, not just
  that one user. 60,000 characters is within the limit the system itself advertises.

- **The first real deployment will fail.** A database upgrade step is written in a way that works
  on the simple local test database but **crashes on the real production database** if any data
  already exists.

- **Confidential keys can leak in error messages.** When something goes wrong, the raw technical
  error is sent back to the user, and those errors frequently contain database passwords or API keys.

## 1.6 What is genuinely good

It would be unfair to leave this out. A real audit says what is right as well as what is wrong:

- **Permissions are done properly.** I checked all 24 entry points. Every administrator function
  is correctly protected, and if someone is demoted their access is revoked immediately.
- **No SQL injection** — the classic database attack is absent throughout.
- **The login token system uses the right cryptographic settings**, avoiding a well-known family
  of forgery attacks.
- **The database design is consistent** and the upgrade history is clean (one defect, noted above).
- **When the AI returns a malformed answer, the system recovers gracefully** instead of crashing —
  this is thoughtful engineering that many teams skip.
- **Odd inputs don't crash it** — empty documents, single sentences, Japanese and Hindi text all
  handled safely.

The problems are not a sign of a bad developer. They cluster into two very human patterns:
**unsafe settings left switched on from the development phase**, and **a system upgraded without
removing the thing it replaced.**

## 1.7 What to fix, in order

| # | Fix | Why this order | Rough effort |
|---|---|---|---|
| 1 | Repair the broken test suite | Nothing else can be verified until the safety net works | Minutes |
| 2 | Fix the crash that takes the service offline | Active, and deliberately triggerable | Minutes |
| 3 | Lock down the default login settings | Easiest to exploit, worst consequence | Hours |
| 4 | Fix the Google sign-in flow | Account takeover | Hours |
| 5 | Fix the text-corruption bug | It damages users' work | Hours |
| 6 | Restrict which websites the extension reads | Blocks Chrome Web Store approval | 1 day |
| 7 | Reconnect or remove the dead admin settings | Silently misleading editors | 1–2 days |
| 8 | Fix "Ready to Publish" and the freeze | Wrong answers, poor performance | 1 day |

**Before any real user touches this:** items 1–6.
**Before anyone trusts a score:** item 7.

**Overall assessment:** roughly **1–2 weeks** of focused work to reach a safe internal pilot.
The foundation is solid and worth building on — this is a fixable project, not a rewrite.

---
---

# PART 2 — For engineers

All paths relative to the repository root. Line numbers are from commit `c53b231`.

## 2.0 Verification method

Findings were produced by reading source, then **confirmed by execution** where possible:

- Backend venv created (Python 3.14.6), `requirements.txt` installed, `pytest` run.
- Extension: `npm install`, `tsc --noEmit`, `vitest run`, `wxt build` all executed.
- Three defects reproduced with standalone scripts against the real modules (B2, H3, M-grammar).
- Import graph and migration/model parity checked by AST analysis.

Results: backend **7 failed / 39 passed**; extension typecheck, tests and build all clean;
`npm audit` reports 21 vulnerabilities (5 critical, 10 high).

---

## 2.1 BLOCKERS

### B1 — Test suite fails on Python ≥3.12; CI is red on `main`

**Files:** `apps/backend/tests/test_evaluation.py:43`, `apps/backend/tests/test_llm_evaluator.py:52`

```python
def _run(req: EvaluationRequest):
    return asyncio.get_event_loop().run_until_complete(MockEvaluator().evaluate(req))
```

`asyncio.get_event_loop()` no longer creates a loop implicitly on the main thread and raises
`RuntimeError: There is no current event loop`. `.github/workflows/ci.yml` pins
`python-version: "3.12"`, so **CI fails as committed**. 7 tests affected.

**Fix** — both files:

```python
def _run(req: EvaluationRequest):
    return asyncio.run(MockEvaluator().evaluate(req))
```

```python
def _run(ev, req):
    return asyncio.run(ev.evaluate(req))
```

Consider adding `pytest-asyncio` and native `async def` tests instead. Also add `3.13`/`3.14`
to a CI matrix so this class of breakage surfaces early.

---

### B2 — Rate limiter self-destructs → HTTP 500 for every new client (REPRODUCED)

**File:** `apps/backend/app/middleware.py:33`, `:44`, `:51`

```python
self._hits: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))   # 33
...
w, count = self._hits[key]                                             # 44
...
if len(self._hits) > 10000:
    self._hits = {k: v for k, v in self._hits.items() if v[0] >= window - 1}   # 51
```

Line 51 **rebinds `self._hits` to a plain `dict`**, destroying the `defaultdict` factory. The
next request with an unseen key raises `KeyError` at line 44 — inside `dispatch`, before
`call_next` — producing a 500. Permanently, for every new key, until worker restart.

Reproduction output:

```
type after cleanup: dict
CONFIRMED KeyError -> 'brand-new-ip:100' = HTTP 500 for every new client
```

Secondary defect: the predicate `v[0] >= window - 1` retains both the current and previous
window, so under load the dict never drops below 10,000 and the O(n) rebuild re-runs on
*every* subsequent request.

**Remotely triggerable** — see M2; `X-Forwarded-For` is attacker-controlled, so 10k distinct
keys can be minted in seconds.

**Fix** (preferred — removes the `defaultdict` dependency entirely):

```python
w, count = self._hits.get(key, (0, 0))
...
if len(self._hits) > 10000:
    self._hits = {k: v for k, v in self._hits.items() if v[0] >= window}
```

Add a regression test that pushes past 10,000 keys — `tests/test_hardening.py:49-70` never
reaches the threshold.

---

### B3 — Auth fails open on stock defaults

**File:** `apps/backend/app/config.py:58`, `:72`, `:74`; `apps/backend/app/auth/service.py:22`, `:56`

```python
jwt_secret: str = os.getenv("JALEBI_JWT_SECRET", "dev-insecure-change-me")   # 58
allow_dev_login: bool = _bool("JALEBI_ALLOW_DEV_LOGIN", True)                # 72
signup_secret: str = os.getenv("JALEBI_SIGNUP_SECRET", "")                   # 74
```

`_email_allowed` treats empty allow-lists as **allow-any**. Nothing in `create_app()` or
`lifespan` validates any of this.

**Attack chain with defaults:** `POST /api/auth/dev-login {"email": "founder@ties.org"}` →
account created unauthenticated → if that address is in `JALEBI_ADMIN_EMAILS`, auto-promoted to
admin (`auth/service.py:56`). Independently, the signing secret is public in this repo, so
`{"sub":"1","role":"admin"}` can simply be forged.

`.env.production.example` documents all the right values — but documentation is not enforcement.

**Fix** — fail closed at startup in `app/main.py` `lifespan`:

```python
if settings.environment == "production":
    problems = []
    if settings.jwt_secret == "dev-insecure-change-me" or len(settings.jwt_secret) < 32:
        problems.append("JALEBI_JWT_SECRET must be set to a random value of >=32 bytes")
    if settings.allow_dev_login and not settings.signup_secret:
        problems.append("JALEBI_ALLOW_DEV_LOGIN requires JALEBI_SIGNUP_SECRET")
    if not settings.allowed_emails and not settings.allowed_domains:
        problems.append("Set JALEBI_ALLOWED_EMAILS or JALEBI_ALLOWED_DOMAINS")
    if settings.cors_origins == ["*"]:
        problems.append("JALEBI_CORS_ORIGINS must not be '*' in production")
    if problems:
        raise RuntimeError("Unsafe production config:\n  - " + "\n  - ".join(problems))
```

---

### B4 — OAuth callback: no `state` validation, token injected into HTML/JS

**File:** `apps/backend/app/api/routes/auth.py:56`, `:60-83`

```python
state = secrets.token_urlsafe(16)                      # 56 — generated…
return {"authorize_url": oauth.authorize_url(state), "state": state}

async def google_callback(code: str = Query(...), ...):   # 60 — …and never checked
```

Three distinct defects:

1. **No CSRF protection.** `state` is generated and returned, but `google_callback` accepts only
   `code`. Login CSRF / session fixation: an attacker feeds a victim their own `code`.
2. **Context-confusion injection.** `{token!r}` emits a **Python** repr into a **JavaScript**
   string context — different escaping grammars. `{user.email}` is interpolated unescaped.
3. **`postMessage(..., '*')`** broadcasts the bearer JWT to any origin that opened the window.

**Fix:**

```python
import html, json, secrets

_PENDING: dict[str, float] = {}          # replace with signed cookie or Redis in prod

@router.get("/google/login")
async def google_login() -> dict:
    state = secrets.token_urlsafe(32)
    _PENDING[state] = time.time() + 600
    return {"authorize_url": oauth.authorize_url(state), "state": state}

@router.get("/google/callback")
async def google_callback(code: str = Query(...), state: str = Query(...), ...):
    expiry = _PENDING.pop(state, None)
    if expiry is None or expiry < time.time():
        raise HTTPException(400, "Invalid or expired OAuth state.")
    ...
    safe_email = html.escape(user.email)
    origin = settings.oauth_post_message_origin      # explicit, never "*"
    html_body = f"""...<h2>Signed in as {safe_email}</h2>
<script>window.opener && window.opener.postMessage(
  {{type:'jalebi-auth', token:{json.dumps(token)}}}, {json.dumps(origin)});</script>"""
```

Prefer moving to `chrome.identity.launchWebAuthFlow` so the token never renders in a page at all.

---

### B5 — Inline checker applies edits at stale offsets → corrupts user text

**File:** `apps/extension/lib/inline/checker.ts:64-82`, apply path at `:229`

```ts
private async run(): Promise<void> {
  const text = this.field.getText();
  ...
  const resp = await chrome.runtime.sendMessage({ type: 'JALEBI_CHECK', text });
  if (resp?.ok) issues = resp.issues as GrammarIssue[];
  ...
  if (this.destroyed) return;     // ← only guard; no generation token
  this.text = text;
  this.setIssues(issues);
}
```

No request-generation token. Debounce narrows but does not close the window: request A fires →
user types → request B fires → **A resolves after B**. `this.text` is then rewritten to A's older
snapshot while `this.issues` holds B's offsets.

Everything derived from that pairing is wrong — `span()` (`:91`), dictionary keys (`:95`),
`sentenceRange` (`:154`), and rect placement (`:126`). Critically, `apply` (`:229`) calls
`replaceRange(issue.offset, issue.length, …)` against offsets computed for a **different string**:
it silently rewrites the wrong span of the user's live text.

**Fix:**

```ts
private seq = 0;

private async run(): Promise<void> {
  const my = ++this.seq;
  const text = this.field.getText();
  ...
  if (this.destroyed || my !== this.seq) return;   // drop stale responses
  this.text = text;
  this.setIssues(issues);
}
```

And make the apply path defensive — an edit between render and click is the same hazard:

```ts
private apply(issue: GrammarIssue, replacement: string): void {
  if (this.field.getText() !== this.text) { this.schedule(); return; }
  this.field.replaceRange(issue.offset, issue.length, replacement);
}
```

---

### B6 — `<all_urls>` content script exfiltrates arbitrary field input

**Files:** `apps/extension/wxt.config.ts:29`, `entrypoints/inline.content.ts:11`,
`lib/inline/editable.ts:5-16`

```ts
matches: ['<all_urls>'],
excludeMatches: ['https://docs.google.com/document/*'],
```

`isEditable` admits `text`, `search`, `email`, `url`, `tel` and `''` (the type-less default), plus
any `contentEditable`. Contents are POSTed to `getBackendUrl()` — user-settable to **any origin**
(`Settings.tsx:45`), backed by `optional_host_permissions: ['https://*/*', 'http://*/*']`.

The comment at `editable.ts:13-14` claims a mitigation that **does not exist in the code**:

```ts
// Password managers/search widgets often mark things editable we don't want;
// require a reasonable size to avoid tiny one-line search boxes elsewhere.
return el.isContentEditable;      // ← no size check whatsoever
```

Fails Chrome Web Store limited-use policy; a genuine privacy defect regardless.

**Fix** — implement the promised filter and exclude sensitive contexts:

```ts
const SENSITIVE_AC = /^(cc-|one-time-code|current-password|new-password|cc-number)/i;

export function isEditable(el: Element | null): el is HTMLElement {
  if (!el || !(el instanceof HTMLElement)) return false;
  if (el.closest('form')?.querySelector('input[type=password]')) return false;
  const ac = el.getAttribute('autocomplete') ?? '';
  if (SENSITIVE_AC.test(ac)) return false;
  if (el instanceof HTMLInputElement) {
    if (el.type === 'password') return false;
    return INPUT_TYPES.has(el.type) && !el.readOnly && !el.disabled;
  }
  if (el instanceof HTMLTextAreaElement) return !el.readOnly && !el.disabled;
  if (!el.isContentEditable) return false;
  const r = el.getBoundingClientRect();          // the check the comment promised
  return r.width >= 240 && r.height >= 40;
}
```

Additionally: move `<all_urls>` to opt-in per-site via `optional_host_permissions`; drop
`http://*/*`; validate the backend URL against an org allow-list; surface the destination host
in Settings.

---

## 2.2 HIGH

### H1 — Rubric system and 4 evaluators are unreachable; admin rubric endpoint is inert

**File:** `apps/backend/app/llm/registry.py:154-161`

```python
def build_evaluator(provider_id: str, retriever=None):
    spec = get_spec(provider_id)
    from app.pipeline.hybrid_evaluator import HybridEvaluator
    client = None if spec.kind == "mock" else _build_client(spec)
    return HybridEvaluator(...)      # every provider, unconditionally
```

Verified live scoring path: `HybridEvaluator` → `engine.combine` → `constitution.weights_for()`
(`engine.py:54`), a **hardcoded module dict**. It never reads `app/rubrics`.

Confirmed by import graph — zero importers outside `app/pipeline/` for `multi_agent.py`,
`orchestrator.py`, `llm_evaluator.py`, `claude_evaluator.py`. `app/rubrics` is imported by routes
(for catalogues and admin writes) but by **no live scoring code**.

Two user-visible consequences:

- **`PUT /api/admin/rubrics/{content_type}` is a silent no-op.** It persists via `set_override`,
  reloads at startup (`main.py:57`), returns updated weights — and changes no score. Editors tune
  weights and see zero effect, with no warning.
- **`JALEBI_PIPELINE=multi` cannot be enabled.** It is read only by `health.py:21` and never acted
  on, despite being documented as shipped in the README and `ARCHITECTURE.md`.

**Fix** — pick one and be decisive:

*Option A (preserve the feature):* have `engine.combine` accept overrides sourced from the rubric
store, mapping the two dimension vocabularies:

```python
# engine.py
weights = C.weights_for(content_type)
override = get_weight_override(content_type)   # from app.rubrics store
if override:
    weights = {**weights, **override}
```

*Option B (cut the dead weight):* delete `orchestrator.py`, `llm_evaluator.py`, `multi_agent.py`,
`claude_evaluator.py`, `mock_reviewer.py`, `aggregate.py`, `prompt.py` and `app/rubrics/`, then
repoint the admin UI at `constitution.WEIGHTS_BY_TYPE`.

**Interim, ship today:** make the endpoint return `501 Not Implemented` rather than lie, and
remove the multi-agent claim from the docs.

---

### H2 — `publication_ready` ignores critical issues

**File:** `apps/backend/app/scoring/engine.py:93` vs `:96-113`

```python
readiness_label, ready = C.band_for(overall)     # 93 — decided here, from score bands only
readiness = PublicationReadiness(readiness_label)

critical: List[Issue] = []                       # 96 — …but critical issues collected here
for cap in sorted(rules.caps, key=lambda c: c.ceiling):
    critical.append(...)
for c in categories:
    for i in c.issues:
        if i.priority in (Priority.critical, Priority.high):
            critical.append(i)
```

A document scoring ≥85 with model-reported `critical` issues is returned as **"Ready to Publish",
`publication_ready=True`**. Hard caps constrain this, but AI-detected critical issues trigger no
cap, so they never influence the verdict.

The correct policy already exists at `aggregate.py:26` (`judge_readiness` checks `has_critical`) —
but that module is on the dead path from H1.

**Fix** — move the decision below the assembly and gate it:

```python
# ... after `critical` is built and sorted ...
if any(i.priority == Priority.critical for i in critical):
    readiness_label, ready = "Not Ready", False
else:
    readiness_label, ready = C.band_for(overall)
readiness = PublicationReadiness(readiness_label)
```

---

### H3 — `/api/check` blocks the event loop ~4.2 s (MEASURED)

**File:** `apps/backend/app/grammar/heuristic.py:176-186`, via `async def check` in
`app/grammar/service.py:18`

```python
def contained(a: GrammarIssue) -> bool:
    a_end = a.offset + a.length
    for b in unique:            # O(n²) over all issues
        ...
return [i for i in unique if not contained(i)]
```

Synchronous O(n²) work called directly from an `async def` handler — it stalls the **entire
worker**, not just the caller. Measured on the real module:

```
chars=60000 issues=3288 heuristic.check took 4179 ms (blocking the event loop)
```

60,000 chars is within `max_document_chars`, and `/api/check` is the **real-time inline** endpoint.
Cost is quadratic, so 4× the issues ≈ 16× the time.

**Fix (both parts):**

1. Linear sweep instead of all-vs-all:

```python
unique.sort(key=lambda i: (i.offset, -i.length))
out, best_end, best_len = [], -1, 0
for i in unique:
    if i.offset >= best_end or not (i.offset + i.length <= best_end and i.length < best_len):
        out.append(i)
    if i.replacements and i.offset + i.length > best_end:
        best_end, best_len = i.offset + i.length, i.length
return out
```

2. Offload regardless, so CPU work never touches the loop:

```python
import anyio
issues = await anyio.to_thread.run_sync(heuristic.check, text)
```

Also apply a smaller cap to `/api/check` (say 10k chars) than the 60k document limit.

---

### H4 — Google Docs extraction: broken fallback, misleading error

**Files:** `apps/extension/lib/doc.ts:26-35`, `entrypoints/content.ts:39-48`

`fetchDocText` is imported by **both** the content script and the background worker. In the worker
there is no `docs.google.com` context, so the export fetch is cross-origin; the **302 to
`accounts.google.com`** (multi-account profiles — the common newsroom case) is not in
`host_permissions` and fails opaquely. `res.ok` then passes on a 200 HTML login page, caught only
by a crude body sniff (`/^\s*<(!doctype|html)/i`).

Separately, `content.ts:39-48` has two disjoint branches. If `resp.ok === true` but `resp.text === ''`,
neither runs, the fallback is skipped, and the user is told **"The document appears to be empty"**
when the fallback would have succeeded.

**Fix:**

```ts
// content.ts — single fallback condition
let text = '';
const resp = await chrome.runtime.sendMessage({ type: 'JALEBI_FETCH_DOC', docId });
if (resp?.ok && resp.text) text = resp.text;
else text = await fetchDocText(docId);      // same-origin here; genuinely works
```

```ts
// doc.ts — diagnose instead of sniffing
if (res.redirected && /accounts\.google\.com/.test(res.url)) {
  throw new Error('Signed into multiple Google accounts — open this doc in the right profile.');
}
if (!res.headers.get('content-type')?.startsWith('text/plain')) {
  throw new Error('Google returned an unexpected response. Reload the doc and retry.');
}
```

Best: perform the export fetch **only** in the content script, where the same-origin claim in the
doc-comment is actually true.

---

### H5 — No timeouts or retries on any LLM client

**Files:** `apps/backend/app/llm/client.py:66`, `app/llm/openai_client.py:63,67`,
`app/llm/gemini_client.py:27`

None pass a timeout or `max_retries`; they inherit SDK defaults (~600 s).
`HybridEvaluator._call_with_repair` then loops `max_attempts=2`, so a stalled provider holds a
request **and its DB session** for ~20 minutes. `MultiAgentEvaluator` fans out concurrently,
multiplying it.

The rest of the codebase gets this right — `auth/oauth.py:34` (15 s),
`grammar/languagetool.py:34` (8 s), `integrations/notify.py:15` (8 s).

**Fix:**

```python
AsyncAnthropic(api_key=..., timeout=60.0, max_retries=2)
AsyncOpenAI(api_key=..., base_url=..., timeout=60.0, max_retries=2)
# Gemini: http_options={"timeout": 60_000}
```

Bound concurrent fan-out with `asyncio.wait_for(asyncio.gather(*tasks), timeout=120)`.

---

### H6 — Migration adds NOT NULL columns with no server default → prod deploy fails

**File:** `apps/backend/migrations/versions/848eaac5682b_document_sop_fields.py:22-25`

```python
batch_op.add_column(sa.Column('status', sa.String(length=30), nullable=False))
batch_op.add_column(sa.Column('editor', sa.String(length=200), nullable=False))
batch_op.add_column(sa.Column('published_for', sa.String(length=200), nullable=False))
batch_op.add_column(sa.Column('co_authors', sa.String(length=500), nullable=False))
```

Models declare Python-side `default=` (`models.py:48-51`), which SQLAlchemy applies on INSERT only —
it emits **no DDL**. On Postgres, `ADD COLUMN ... NOT NULL` without a default against a non-empty
table raises. The Dockerfile runs `alembic upgrade head` on every container start, so this is a hard
deploy failure wherever `documents` already has rows.

It passes today only because dev uses SQLite with `render_as_batch=True` (`migrations/env.py:38`),
which rebuilds the table and masks it until the first real Postgres deploy.

**Fix:**

```python
batch_op.add_column(sa.Column('status', sa.String(30), nullable=False, server_default='draft'))
batch_op.add_column(sa.Column('editor', sa.String(200), nullable=False, server_default=''))
batch_op.add_column(sa.Column('published_for', sa.String(200), nullable=False, server_default=''))
batch_op.add_column(sa.Column('co_authors', sa.String(500), nullable=False, server_default=''))
```

Optionally drop the server defaults in a follow-up revision once backfilled.

---

### H7 — Inline checkers never destroyed → unbounded SPA leak

**File:** `apps/extension/entrypoints/inline.content.ts:24-51`

Only `focusin` is handled. When a focused field leaves the DOM (SPA route change, modal close,
Gmail compose closed), nothing calls `detach()`. Each orphan retains `window` scroll/resize
listeners (`checker.ts:45-46`, capture phase), a `document` `mousemove` capture listener
(`hovercard.ts:50`), a `storage.onChanged` listener (`dictionary.ts:38`), and three
`document.body` children — one leaked checker **per field ever focused**, each doing rAF
repositioning on every scroll event.

On Gmail/Notion/LinkedIn — the stated targets — this accumulates for the whole session.

**Fix:**

```ts
const mo = new MutationObserver(() => {
  if (currentEl && !currentEl.isConnected) detach();
});
mo.observe(document.body, { childList: true, subtree: true });
window.addEventListener('pagehide', detach, { once: true });
```

Also register `chrome.storage.onChanged` only when `enabled`, and remove it on teardown.

---

## 2.3 MEDIUM

| ID | File:line | Issue | Fix |
|---|---|---|---|
| M1 | `config.py:125` | CORS defaults to `*`. `allow_credentials=False` is correct, but this API authenticates by `Authorization` header with `allow_headers=["*"]` — not covered by that flag. Any origin can drive the admin API with a leaked token. | Default to `[]`; require explicit list; refuse `*` in production. |
| M2 | `middleware.py:17-22` | `X-Forwarded-For` trusted unconditionally. Rate limiting is bypassable per request; also poisons audit-log IPs; is the trigger for **B2**. Uvicorn started without `--proxy-headers`. | Honor XFF only when the peer is in a configured trusted-proxy CIDR set. |
| M3 | `rewrite.py:96`, `health.py:39` | Provider/DB errors echoed to clients. SDK exceptions embed URLs/org ids/truncated keys; SQLAlchemy errors commonly include **the DSN with credentials**. `/api/health/ready` is unauthenticated. | Log server-side with request id; return generic text and `{"status":"degraded"}`. |
| M4 | `dashboard/views.py:120` | Stored XSS. `<a href="${d.url}">${d.title}</a>` via `innerHTML`, from `doc_url`/`title` — unvalidated free text on `/api/evaluate`, unauthenticated by default. Fires in an **admin's** browser → writer→admin escalation. | Add `esc()` on every interpolation; allow-list `https:` hrefs; add CSP with a nonce. |
| M5 | `admin.py:88-101`, `rubrics/__init__.py:311` | Override validates keys only. All-zero → `or 1.0` → every weight `0.0` → all documents score 0. Negatives invert scores. `accuracy: 0.90` silently stores `0.5233` after renormalisation and reports the rescaled value back. | Require finite `>= 0`; reject `sum <= 0`; `if total <= 0: return base`. |
| M6 | `engine.py:71` | In the rules-only path `ai_s = _q5(rule_s)` — the rule score is quantised and blended into itself, drifting ±2 per dimension in the mode the docstring calls "rules-only". | `final = rule_s if d.key not in ai.dim_scores else round(blend)`. |
| M7 | `services/analytics.py:22`, `documents.py:18` | `select(Evaluation)` with no pagination pulls the whole `result` JSON (10–50 kB/row) into Python on every dashboard load. | SQL aggregation (`func.count/avg/group_by`) as `admin.py:149` already does; `load_only()`; date window. |
| M8 | `lib/types.ts:52` vs `evaluation.py:88` | `EvaluationMeta`: every backend field except `content_type` has a default; TS declares all 7 **required**. `Scorecard.tsx:31-36` reads them unguarded → `undefined` in UI. `AuthUser` missing `department`; `classify`/`providers` return untyped `dict`. | Mark optional in TS; add `response_model=`; generate types from OpenAPI. |
| M9 | `lib/api.ts:74` | FastAPI 422 returns `detail` as an **array of objects** → React "Objects are not valid as a React child" → white screen. No `AbortController`/timeout, so a hung backend pins the panel in `evaluating` forever. | Coerce `detail` to string; add timeout + abort. |
| M10 | `ReviewCanvas.tsx:156,166` | `w.replace(m.quote, …)` replaces the **first** occurrence, not the marked one; `$&`/`$1` in model output is interpreted as a replacement pattern (a model emitting `"$1,000"` corrupts output). | Replace by `start`/`end` index, descending order, function replacement `() => m.expected`. |
| M11 | `grammar/heuristic.py:109-112` | **Verified false positives on correct English:** `"a university"`→"an university", `"an hour"`→"a hour", `"a European"`→"an European", `"an FBI"`→"a FBI". Rule matches orthography, not phonetics. Space-before-punct rule matches across newlines → applying the fix **deletes paragraph breaks**. | Exception lists for `h`/`eu`/`u`/acronyms; restrict to `[ \t]+`; add `(?<!\d)` and skip URL spans. |
| M12 | `knowledge/store.py:85` | `abs(hash(id)) % 10**18` — Python's `hash()` is randomized per process, so Qdrant point ids differ across restarts and `upsert` never updates; it accumulates duplicates. | `int(hashlib.sha1(id.encode()).hexdigest()[:15], 16)`. |
| M13 | `knowledge/embeddings.py:36` | `OpenAI(api_key=settings.anthropic_api_key or None)` — sends an `sk-ant-…` key to `api.openai.com`. Failure is swallowed, so it degrades silently. | Read `OPENAI_API_KEY`. |
| M14 | `config.py:55`, `registry.py` | `claude-opus-4-8` is not a valid Anthropic model id; an `anthropic` request with no `JALEBI_MODEL` fails at call time, not startup. | Use a current model id; validate at startup. |
| M15 | `vitest.config.ts:11` | `environment: 'node'` → no DOM test can run. Every risky module here (`rects.ts`, `editable.ts`, `checker.ts`, `overlay.ts`) is **untested**; the 2 test files cover pure string helpers. No `exclude` for `node_modules`. | Switch to `jsdom`; add `exclude`; add `*.test.tsx`. |
| M16 | `package.json` | 21 npm vulnerabilities (5 critical, 10 high); WXT 0.19 well behind current. | `npm audit fix`; plan a WXT upgrade. |
| M17 | `main.py:44-66` | Startup wraps seeding/reindex/override-load in a bare `except` that only `print()`s → silently empty vector store or unapplied weights. `InMemoryStore` is per-worker, so RAG results vary by worker under Gunicorn. | `logger.exception`; fail startup on override-load error; require `QDRANT_URL` when workers > 1. |

Also worth fixing: `rects.ts` drops continuation rects for wrapped lines and never clips to the
field box (underlines float over the page); `editable.ts:34-46` flattens inline markup on
contenteditable and doesn't restore the caret; `docs.ts` fires comment jobs **before** awaiting
`batchUpdate` (partial writes, no rollback) and overwrites stored highlight ranges so earlier
highlights can never be cleared.

---

## 2.4 What is correct — verified, not assumed

- **RBAC complete.** All 24 routes mapped. Every `/api/admin/*` carries `Depends(admin_only)`.
  `require_role` reads `user.role` from a freshly-fetched row, not the JWT claim, so demotion is
  effective immediately.
- **No SQL injection.** All queries use bound Core/ORM constructs; the only raw SQL is a constant
  `text("SELECT 1")` in the health probe.
- **JWT handling correct.** Explicit `algorithms=["HS256"]` — no `alg:none`/algorithm confusion.
  `exp` set and verified.
- **Zero broken imports** across 73 modules (AST-checked).
- **Migrations match models** on every column and index across all 6 tables; revision chain is
  linear. H6 is the only defect.
- **LLM JSON-repair path is genuinely good** — catches parse failures, feeds the error back for one
  repair attempt, degrades to a rules-only report rather than erroring. `ai_prompt.parse` clamps
  scores and filters placeholder echoes.
- **Edge inputs safe.** Empty / single-sentence / unicode / no-citation inputs exercised: division
  guards hold, CJK titles safe, all rubric weight vectors sum to exactly 1.0.
- **TypeScript is `strict: true`**, almost no `any`, no `dangerouslySetInnerHTML`; model-returned
  content reaches the DOM via `textContent` or JSX text children.

---

## 2.5 Recommended sequence

**Sprint 1 — stop the bleeding (1–2 days)**
`B1` (unblocks verification) → `B2` → `B3` → `B4` → `M2` → `M1`

**Sprint 2 — protect the user (2–3 days)**
`B5` → `B6` → `H7` → `M9` → `M10` → `M11`

**Sprint 3 — make the scores mean something (3–4 days)**
`H1` (decide the engine story) → `H2` → `M5` → `M6` → `H3`

**Sprint 4 — deployability (2 days)**
`H6` → `H5` → `M3` → `M4` → `M7` → `M17` → `M16`

**Then:** `M15` (DOM tests) and raise coverage on `checker.ts` / `rects.ts` / `editable.ts`, which
carry the highest user-facing risk and currently have none.

### Guardrails worth adding

- CI matrix across Python 3.12/3.13/3.14 — B1 would have been caught immediately.
- A production config smoke-test asserting the app **refuses to boot** with unsafe defaults (B3).
- A regression test pushing the limiter past 10,000 keys (B2).
- Generate `lib/types.ts` from the FastAPI OpenAPI schema to end schema drift (M8) — the file
  header already commits to this.
