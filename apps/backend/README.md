# Jalebi backend

FastAPI service: scoring engine, editorial workflow, fact-check surfacing, RAG
knowledge base, auth, and a server-rendered dashboard.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Works on an empty `.env`: SQLite, in-memory vectors, no API key. About 72% of the score
is deterministic, so it produces real results with nothing configured.

- API docs — `/docs`
- Dashboard — `/dashboard`
- Health — `/api/health`

Optional extras: `pip install openai` for GPT and the OpenAI-compatible providers,
`google-genai` for Gemini, `asyncpg` for Postgres, `qdrant-client` for a shared vector
store.

## Tests

```bash
pytest -q          # 349 tests, no API key, no network
```

`tests/conftest.py` pins `JALEBI_PROVIDER=mock` and an isolated temp database, so the
suite is deterministic and costs nothing. No test makes a live provider call.

## API

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/api/health`, `/api/health/ready` | — | Liveness, readiness |
| GET | `/api/providers`, `/api/content-types` | — | Catalogues |
| POST | `/api/evaluate` | optional | Score a document |
| POST | `/api/classify` | optional | Detect content type |
| POST | `/api/check` | optional | Real-time grammar (inline checker) |
| POST | `/api/rewrite` | optional | Sentence rewrite options |
| POST | `/api/integrity` | optional | Claims, citation gaps, bias |
| POST | `/api/factcheck` | optional | Ranked fact-check worklist |
| POST | `/api/nation-first` | optional | Editorial red-line review queue |
| POST | `/api/auth/dev-login` · GET `/api/auth/google/*`, `/api/auth/me` | — | Auth |
| GET | `/api/evaluations`, `/api/evaluations/{id}` | user | History (own; all for editor+) |
| GET/PUT | `/api/documents`, `/api/documents/{id}/…` | editor | Tracker, workflow, integrity |
| GET | `/api/analytics/overview` | editor+ | Dashboard metrics |
| GET/POST/DELETE | `/api/knowledge*` | editor/admin | Knowledge base |
| — | `/api/admin/*` | admin | Users, scoring weights, prompts, audit log, usage |

## Layout

```
app/
  main.py                 app factory, lifespan, production safety gate
  config.py               every setting, plus the production gate itself
  middleware.py           rate limiting, security headers, request logging

  scoring/
    constitution.py       dimensions, weights, caps, bands, source tiers
    rules.py              the deterministic engine
    reasoning.py          insight/depth/narrative from reasoning structure
    engine.py             blend, caps, readiness, summary
    ai_prompt.py          system prompt + tolerant response parsing
    sop_header.py         SOP metadata block parsing
    sop_compliance.py     word window, structure, references

  analysis/
    factcheck.py          ranked claim worklist
    analyzers.py          claims, citation gaps, bias, absolutes
    nation_first.py       editorial red lines (flags, never a score penalty)

  workflow/
    states.py             production-loop state machine + SLA windows
    service.py            transitions, assignment, sign-off

  pipeline/
    hybrid_evaluator.py   the only evaluator: rules + optional AI judgment
    text_features.py      surface features
    classifier.py         content-type detection
    base.py               Evaluator interface

  text/sentences.py       shared sentence splitter (see its docstring)
  llm/                    provider registry + Anthropic/OpenAI/Gemini clients
  knowledge/              embeddings, vector store, RAG retrieval, seeding
  auth/                   JWT, Google OAuth, roles
  db/                     async SQLAlchemy models and session
  services/               history, analytics, documents, audit
  dashboard/views.py      server-rendered admin UI (no build step)
```

## Design notes

**One evaluator.** `HybridEvaluator` serves every provider; `mock` is the same class
with no client. Earlier `MockEvaluator`/`ClaudeEvaluator`/`MultiAgentEvaluator` classes
and the `app/rubrics` weighting vocabulary became unreachable and were deleted.

**Sentence splitting lives in one place.** `app/text/sentences.py`. It was
reimplemented four times, and every copy split `12.7%` into `12.` and `7%` and severed
`Dr. Rao` from its claim — which meant an attributed statement could be analysed as
unattributed. Do not add a local regex.

**Scoring is explainable.** Rules produce quoted issues; the AI layer is constrained to
judgment it cannot fabricate. A provider timeout degrades to rules-only rather than
failing the request.

See [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) for the reasoning behind
these, and [../../docs/CONFIGURATION.md](../../docs/CONFIGURATION.md) for every setting.
