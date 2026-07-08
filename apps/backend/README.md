# Jalebi Backend

FastAPI platform: editorial review pipeline over any AI provider, plus auth, history,
a RAG knowledge base, a founder/editor dashboard + admin panel, and research-integrity
analysis. Runs with **zero infrastructure** (SQLite + in-memory vectors + mock provider)
and scales up via environment variables.

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional — defaults already run
uvicorn app.main:app --reload
```

- Swagger: http://127.0.0.1:8000/docs
- Dashboard + admin: http://127.0.0.1:8000/dashboard
- Health: http://127.0.0.1:8000/api/health

## Test

```bash
source .venv/bin/activate && pytest -q
```

## Choosing an AI provider

Set `JALEBI_PROVIDER` and the matching key/model (see `.env.example`). Configured
providers appear in `/api/providers` and in the extension's model picker; keys never
leave the backend.

| Provider | env |
|----------|-----|
| Claude | `JALEBI_PROVIDER=anthropic` `ANTHROPIC_API_KEY=…` (`JALEBI_MODEL=claude-opus-4-8`) |
| GPT | `JALEBI_PROVIDER=openai` `OPENAI_API_KEY=…` `OPENAI_MODEL=…` |
| Gemini | `JALEBI_PROVIDER=gemini` `GEMINI_API_KEY=…` `GEMINI_MODEL=…` (`pip install google-genai`) |
| Grok | `JALEBI_PROVIDER=xai` `XAI_API_KEY=…` `XAI_MODEL=…` |
| Ollama (local, OSS) | `JALEBI_PROVIDER=ollama` `OLLAMA_MODEL=llama3.1` |
| OpenRouter/Groq/Together/DeepSeek/Mistral | `JALEBI_PROVIDER=<id>` + that provider's key/model |

GPT and all OpenAI-compatible providers need `pip install openai`. `JALEBI_PIPELINE=multi`
runs one reviewer per dimension group concurrently instead of a single call.

## Key endpoints

| Method | Path | Role | Purpose |
|--------|------|------|---------|
| GET | `/api/health`, `/api/providers`, `/api/content-types` | — | status / catalogues |
| POST | `/api/evaluate` | optional | evaluate a document (`provider` override); persists history |
| POST | `/api/classify` | optional | auto-detect content type from the text |
| POST | `/api/integrity` | optional | claim / citation / bias analysis |
| POST | `/api/auth/dev-login` | — | password-less login (gated) |
| GET | `/api/auth/google/login`, `/callback`, `/api/auth/me` | — / user | Google OAuth + profile |
| GET | `/api/evaluations`, `/{id}` | user | history (own; all for editor+) |
| GET/POST/DELETE | `/api/knowledge*` | editor/admin | knowledge base |
| GET | `/api/analytics/overview` | editor+ | dashboard metrics |
| `/api/admin/*` | admin | users, rubric weights, prompts, logs, usage |

## Layout

```
app/
  main.py                 app factory + lifespan (DB init, reindex, override load)
  config.py               all env-driven settings
  schemas/evaluation.py   the scorecard contract
  rubrics/                content-type rubrics + admin weight overrides
  pipeline/
    prompt.py             Editorial DNA + rubric → system prompt (+ RAG)
    text_features.py      heuristic document analysis
    mock_reviewer.py      content-aware mock reviewers
    aggregate.py          shared scoring/readiness policy
    orchestrator.py       MockEvaluator
    llm_evaluator.py      provider-agnostic LLM evaluator (parse/repair/map)
    multi_agent.py        per-dimension multi-agent evaluator
  llm/
    client.py             LLMClient + AnthropicClient
    openai_client.py      OpenAI-compatible (GPT + all OSS hosts)
    gemini_client.py      Gemini
    registry.py           provider catalogue + factory
  knowledge/              embeddings · vector store · ingest/retrieve (RAG)
  db/                     async engine + models (users, evals, docs, KB, audit)
  auth/                   JWT · Google OAuth · roles · deps
  analysis/analyzers.py   research-integrity analyzers (P6)
  integrations/notify.py  Slack / Teams
  services/               history · analytics · audit
  dashboard/views.py      server-rendered dashboard + admin (no build step)
  api/routes/             health providers evaluate integrity auth evaluations
                          knowledge analytics admin
tests/                    mock, llm-evaluator/registry, full e2e platform
```

## Migrations (Alembic)

Dev auto-creates tables on startup (`JALEBI_AUTO_CREATE=true`, the default). For
production set `JALEBI_AUTO_CREATE=false` and manage the schema with Alembic:

```bash
alembic upgrade head                          # apply migrations
alembic revision --autogenerate -m "change"   # after editing app/db/models.py
```

The Dockerfile runs `alembic upgrade head` before serving; env is read from
`JALEBI_DATABASE_URL` (see `migrations/env.py`).

## Deploy

`Dockerfile` (respects `$PORT`; runs migrations), `../../docker-compose.yml`
(backend + Postgres + Qdrant), CI in `../../.github/workflows/ci.yml`.
