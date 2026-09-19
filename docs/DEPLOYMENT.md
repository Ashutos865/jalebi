# Deployment

Running Jalebi somewhere other than a laptop. Every setting referenced here is
described in [CONFIGURATION.md](CONFIGURATION.md).

---

## Before anything else: the production gate

With `JALEBI_ENV=production`, Jalebi **refuses to start** until the development
defaults are corrected. This is intentional — the defaults are convenient and unsafe,
and the first three below combine into "a stranger can create an admin account".

Start-up fails if:

| Condition | Why |
|---|---|
| `JALEBI_JWT_SECRET` is the default, or under 32 chars | The default value is published in this repository, so anyone can forge an admin token |
| `JALEBI_ALLOW_DEV_LOGIN=true` with no `JALEBI_SIGNUP_SECRET` | Passwordless account creation, open to the internet |
| Dev-login on with no email/domain allow-list | Any address may sign in |
| `JALEBI_CORS_ORIGINS` contains `*` | This API authenticates by header, which the credentials flag does not cover, so any site could drive it with a leaked token |

The error message names each problem and its fix. Do not work around it by setting
`JALEBI_ENV=development` on a public host.

---

## 1. Minimum viable production

```bash
# Secrets you generate
JALEBI_JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(48))")

# Identity
JALEBI_ENV=production
JALEBI_ADMIN_EMAILS=editor@example.org
JALEBI_ALLOWED_DOMAINS=example.org
JALEBI_ALLOW_DEV_LOGIN=false          # or set JALEBI_SIGNUP_SECRET
JALEBI_REQUIRE_AUTH=true

# Network
JALEBI_CORS_ORIGINS=https://jalebi.example.org,chrome-extension://<your-extension-id>
JALEBI_TRUSTED_PROXIES=127.0.0.1      # only if behind a reverse proxy

# Data
JALEBI_DATABASE_URL=postgresql+asyncpg://jalebi:...@db:5432/jalebi
JALEBI_AUTO_CREATE=false              # Alembic owns the schema
```

Then:

```bash
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 2. Docker

```bash
docker compose up --build
```

Brings up the backend, Postgres, Qdrant and LanguageTool. The backend image runs
`alembic upgrade head` before serving, and respects `$PORT` so it works unchanged on
Railway or Render.

## 3. Behind a reverse proxy

`Caddyfile` in the repository root is a working example with automatic HTTPS.

**Set `JALEBI_TRUSTED_PROXIES` to your proxy's address.** `X-Forwarded-For` is
attacker-controlled otherwise, and the rate limiter — the only abuse control on the
expensive evaluation path — keys on it. Left empty, the header is ignored entirely,
which is correct for a directly-exposed server but will make every request appear to
come from the proxy when there is one.

## 4. Multiple workers

```bash
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4
```

**Set `QDRANT_URL` when running more than one worker.** The default vector store is
in-memory and per-process, so workers would hold different indexes and RAG results
would vary by which one answered.

The rate limiter is also per-process, so the effective limit is
`JALEBI_RATE_LIMIT × workers`. Use a shared store if you need a strict global limit.

## 5. AI provider

Optional. Jalebi scores without one — roughly 72% of the score is deterministic — and
adding a provider adds judgment on top.

```bash
JALEBI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
JALEBI_ALLOWED_PROVIDERS=anthropic     # constrains /api/evaluate and /api/rewrite
```

The request budget defaults (60s per call, 180s per evaluation) are deliberate: without
them a stalled provider holds a request and its database session for roughly twenty
minutes. Raise them only with a reason.

## 6. The extension

```bash
cd apps/extension
npm ci
npm run build          # .output/chrome-mv3
npm run zip            # for the Chrome Web Store
```

Point it at the deployed backend in the sidebar's settings panel. The URL must be
`https` outside localhost — field contents travel over it.

Note the extension declares broad host access for the inline grammar checker. That is
the main obstacle to a public Web Store listing; see [PRODUCT.md](../PRODUCT.md) §2.1.

## 7. Monitoring

```bash
SENTRY_DSN=https://...
JALEBI_SLACK_WEBHOOK=https://hooks.slack.com/services/...
```

`GET /api/health` is liveness; `GET /api/health/ready` also checks the database and
returns 503 when it is unreachable. The readiness probe deliberately returns no error
detail — database errors routinely embed the connection string, credentials included.

---

## Pre-flight checklist

- [ ] `JALEBI_ENV=production` and the app starts (the gate passes)
- [ ] `JALEBI_JWT_SECRET` is 32+ random characters, not from this repository
- [ ] `JALEBI_ALLOW_DEV_LOGIN=false`, or gated by secret **and** allow-list
- [ ] `JALEBI_CORS_ORIGINS` lists exact origins
- [ ] `JALEBI_TRUSTED_PROXIES` set if and only if behind a proxy
- [ ] `JALEBI_AUTO_CREATE=false` and `alembic upgrade head` run
- [ ] `QDRANT_URL` set if workers > 1
- [ ] HTTPS terminated, HSTS on
- [ ] A restore from backup has actually been tested

## Upgrading

```bash
git pull
pip install -r requirements.txt
alembic upgrade head
```

Migrations are additive and carry `server_default` on every non-nullable column, so they
apply to tables that already hold data. This was not always true — an earlier migration
added four `NOT NULL` columns with no default and would have failed on the first
Postgres deployment with existing rows.
