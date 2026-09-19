# Configuration

Every setting is an environment variable, read once at startup from the process
environment or a local `.env`. Defaults are chosen so that `uvicorn app.main:app`
works on an empty file — SQLite, in-memory vectors, no API key.

**Those defaults are development defaults.** With `JALEBI_ENV=production` the app
refuses to start until the unsafe ones are corrected; see
[the production gate](#the-production-gate).

---

## Core

| Variable | Default | Effect |
|---|---|---|
| `JALEBI_ENV` | `development` | `production` activates the startup safety gate |
| `JALEBI_DATABASE_URL` | `sqlite+aiosqlite:///./jalebi.db` | Async SQLAlchemy URL. Postgres: `postgresql+asyncpg://user:pass@host/db` |
| `JALEBI_AUTO_CREATE` | `true` | Create tables at startup. Set `false` in production and run `alembic upgrade head` |
| `JALEBI_MAX_CHARS` | `60000` | Largest document accepted by `/api/evaluate` |

## AI provider

Jalebi scores without a provider; one adds judgment on top of the rules.

| Variable | Default | Effect |
|---|---|---|
| `JALEBI_PROVIDER` | `mock` | `mock`, `anthropic`, `openai`, `gemini`, `xai`, `ollama`, `openrouter`, `groq`, `together`, `deepseek`, `mistral` |
| `JALEBI_ALLOWED_PROVIDERS` | *(any configured)* | Comma-separated allow-list. Constrains `/api/evaluate` **and** `/api/rewrite` |
| `JALEBI_MODEL` | `claude-sonnet-5` | Model id for Anthropic |
| `ANTHROPIC_API_KEY` | — | Claude |
| `OPENAI_API_KEY` | — | GPT, and the OpenAI embeddings backend |
| `GEMINI_API_KEY` | — | Gemini |
| `JALEBI_EFFORT` | `medium` | Thinking/output effort where the provider supports it |

### Request budget

Without these the SDK defaults (~600s) apply, and because the evaluator retries once on
a malformed reply a stalled provider can hold a request — and its database session —
for roughly twenty minutes.

| Variable | Default | Effect |
|---|---|---|
| `JALEBI_LLM_TIMEOUT` | `60` | Seconds per provider request |
| `JALEBI_LLM_RETRIES` | `2` | SDK-level retries on transient failures |
| `JALEBI_LLM_TOTAL_TIMEOUT` | `180` | Ceiling for a whole evaluation. Exceeding it degrades to rules-only rather than failing |

## Authentication

| Variable | Default | Effect |
|---|---|---|
| `JALEBI_JWT_SECRET` | `dev-insecure-change-me` | **Must be changed.** The default is published in this repository |
| `JALEBI_JWT_TTL_MIN` | `720` | Token lifetime in minutes |
| `JALEBI_ADMIN_EMAILS` | — | Comma-separated; these addresses become admin on first login |
| `JALEBI_ALLOW_DEV_LOGIN` | `true` | Passwordless email login. Gate it or disable it in production |
| `JALEBI_SIGNUP_SECRET` | — | Shared secret required by dev-login |
| `JALEBI_ALLOWED_EMAILS` | — | Exact addresses permitted to sign in |
| `JALEBI_ALLOWED_DOMAINS` | — | Email domains permitted to sign in |
| `JALEBI_REQUIRE_AUTH` | `false` | Require a token on `/api/evaluate` and the other analysis endpoints |

Empty allow-lists mean **any** address may sign in. That is a development convenience,
and the production gate rejects it.

### Google OAuth

| Variable | Default | Effect |
|---|---|---|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | — | OAuth client |
| `GOOGLE_REDIRECT_URI` | `http://127.0.0.1:8000/api/auth/google/callback` | Must match the client's registered URI |
| `JALEBI_OAUTH_POSTMESSAGE_ORIGIN` | *(derived from the redirect URI)* | Exact origin the success page may post the token to. Never `*` |

## Network

| Variable | Default | Effect |
|---|---|---|
| `JALEBI_CORS_ORIGINS` | `*` | Allowed origins. The API authenticates by `Authorization` header, which the credentials flag does not cover, so a wildcard lets any site drive it with a leaked token |
| `JALEBI_TRUSTED_PROXIES` | *(none)* | IPs or CIDR blocks whose `X-Forwarded-For` is honoured. Empty means directly exposed and the header is ignored |
| `JALEBI_RATE_LIMIT` | `60` | Requests per minute per client on `/api/*`. `0` disables |
| `JALEBI_SECURITY_HEADERS` | `true` | HSTS, nosniff, referrer policy |
| `JALEBI_REQUEST_LOG` | `true` | Structured request logging |

`JALEBI_TRUSTED_PROXIES` matters more than it looks: `X-Forwarded-For` is
attacker-controlled on a directly-exposed server, so trusting it unconditionally lets
anyone mint a fresh rate-limit bucket per request. Set it **only** to the address of
your reverse proxy.

## Knowledge base (RAG)

| Variable | Default | Effect |
|---|---|---|
| `JALEBI_RAG_ENABLED` | `true` | Retrieve editorial standards into the prompt |
| `JALEBI_RAG_TOP_K` | `4` | Passages retrieved per evaluation |
| `JALEBI_EMBEDDING` | `hash` | `hash` (no dependencies) or `openai` |
| `QDRANT_URL` | *(in-memory)* | Vector store. **Required when running more than one worker** — the in-memory store is per-process, so workers would disagree. Enforced: see below |
| `WEB_CONCURRENCY` | `1` | Worker count. Read only to detect the multi-worker case above; your process manager sets the actual concurrency |
| `QDRANT_API_KEY` | — | Qdrant auth |

## Grammar

| Variable | Default | Effect |
|---|---|---|
| `JALEBI_LANGUAGETOOL_URL` | *(heuristic)* | LanguageTool server for the inline checker. Empty uses the built-in heuristic rules |

## Integrations

| Variable | Default | Effect |
|---|---|---|
| `JALEBI_SLACK_WEBHOOK` | — | Workflow handoffs and sign-offs |
| `JALEBI_TEAMS_WEBHOOK` | — | As above |
| `JALEBI_NOTIFY_ON_READY` | `false` | Announce when a piece becomes publication-ready |
| `SENTRY_DSN` | — | Error monitoring |

---

## The production gate

With `JALEBI_ENV=production`, startup fails — loudly, before serving a request — if any
of these hold:

- `JALEBI_JWT_SECRET` is the published default, or shorter than 32 characters
- `JALEBI_ALLOW_DEV_LOGIN=true` with no `JALEBI_SIGNUP_SECRET`
- `JALEBI_ALLOW_DEV_LOGIN=true` with no email or domain allow-list
- `JALEBI_CORS_ORIGINS` contains `*`
- `WEB_CONCURRENCY > 1` with RAG enabled and no `QDRANT_URL`

The last one is not a security problem but a correctness one: the in-memory
vector store is per-process, so the same document would retrieve different
supporting passages depending on which worker answered. Outside production it is
logged as a warning rather than blocking startup.

The error names every problem and how to fix it. This is deliberate: each of these
defaults is safe in development and dangerous in production, and the combination of the
first three is enough for a stranger to create an admin account.

The gate is inert outside production, so the zero-configuration development path still
works.

## Removed settings

| Variable | Note |
|---|---|
| `JALEBI_PIPELINE` | Selected a multi-agent evaluator that was unreachable dead code. Removed with it; every provider runs through `HybridEvaluator` |
| `JALEBI_EVALUATOR` | Legacy alias for `JALEBI_PROVIDER`; still mapped for backwards compatibility |
