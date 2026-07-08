# Jalebi — Production Deployment (VPS)

A hardened deploy for ~100 internal users. Auth model: **email + shared-secret login**
with an email allow-list (no Google OAuth required).

## 0. What you provide

- A VPS (2 vCPU / 2 GB RAM is plenty) with Docker, or Python 3.12 + Postgres.
- A domain pointing at the VPS (for HTTPS).
- One AI provider key (e.g. Anthropic).
- Two secrets you invent: `JALEBI_JWT_SECRET` (32+ random chars) and
  `JALEBI_SIGNUP_SECRET` (the shared secret you hand to your users).

## 1. Configure

```bash
cd apps/backend
cp .env.production.example .env
# edit .env — fill every REQUIRED value
```

Generate strong secrets:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # run twice
```

Key auth settings (this is the hardening that closes the open-admin backdoor):

| Var | Purpose |
|-----|---------|
| `JALEBI_SIGNUP_SECRET` | Required to log in. Share with approved users only. |
| `JALEBI_ALLOWED_DOMAINS` / `JALEBI_ALLOWED_EMAILS` | Only these can sign in. |
| `JALEBI_ADMIN_EMAILS` | Auto-promoted to admin. |
| `JALEBI_REQUIRE_AUTH=true` | `/evaluate` requires a token (protects your AI spend). |
| `JALEBI_CORS_ORIGINS` | Lock to your dashboard + published extension id. |

## 2a. Run with Docker (recommended)

```bash
# from repo root
docker compose up --build -d
```
Brings up backend (runs `alembic upgrade head` on start) + Postgres + Qdrant. Pass your
secrets via a root `.env` or the shell environment (see `docker-compose.yml`).

## 2b. Run without Docker

```bash
cd apps/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt asyncpg qdrant-client
alembic upgrade head                       # apply migrations (AUTO_CREATE=false)
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run it as a service (systemd) and keep it bound to `127.0.0.1` — Caddy handles the public port.

## 3. HTTPS (Caddy)

Point your domain's DNS at the VPS, edit the domain in `../Caddyfile`, then:

```bash
caddy run --config ./Caddyfile     # auto-provisions + renews TLS
```

Now `https://jalebi.example.com/dashboard` and `/api/*` are live over TLS.

## 4. Scaling / workers

- A **single uvicorn process** comfortably serves ~100 users. To use more workers:
  `gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2`.
- **If you run more than one worker, use Postgres + Qdrant** (set `QDRANT_URL`). The
  in-memory vector store and admin rubric-weight overrides are per-process; with Qdrant
  the KB is shared, and rubric overrides reload on each worker's startup (so an admin
  weight change propagates on the next restart/rolling deploy — fine for infrequent
  config changes). For instant propagation across workers, keep a single worker.

## 5. First-run checklist

- [ ] `.env` has all REQUIRED values; `JALEBI_AUTO_CREATE=false`.
- [ ] `alembic upgrade head` ran (Docker does this automatically).
- [ ] `curl https://your-domain/api/health/ready` returns `{"status":"ready"}`.
- [ ] Log into `/dashboard` with an admin email + the shared secret → you're admin.
- [ ] Seed the knowledge base (Knowledge tab) if using RAG.
- [ ] `JALEBI_REQUIRE_AUTH=true`, `JALEBI_CORS_ORIGINS` locked, dev secret set.

## 6. Extension distribution

- Build: `cd apps/extension && npm install && npm run build` → `.output/chrome-mv3`.
- Zip it (`npm run zip`) and publish **privately/unlisted** on the Chrome Web Store, or
  distribute via your org's managed-Chrome policy for the ~100 users.
- Users open the side panel → ⚙ Settings → set the **Backend URL** to your domain and
  **Sign in** with their email + the shared secret. The token is stored and sent on
  every request.

## 7. Backups & monitoring

- **Backups:** `pg_dump` the Postgres DB on a schedule; snapshot the Qdrant volume.
- **Monitoring:** set `SENTRY_DSN` for error tracking. Request logs (method/path/status/
  latency/IP + `X-Request-ID`) go to stdout — ship them to your log aggregator.
- **Health probes:** liveness `GET /api/health`, readiness `GET /api/health/ready`.
