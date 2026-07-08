# Jalebi

**AI-powered editorial quality-assurance system for TIES.**

Jalebi is not a grammar checker. It is a Managing-Editor-in-software: it evaluates an
article, script, or report against TIES' editorial standards, explains what is weak and
why, tells the writer how to fix it, and decides whether the piece is ready to publish.

It ships as a Chrome extension that works inside Google Docs, backed by a FastAPI
platform that runs a multi-stage **editorial review pipeline** over any AI provider you
choose.

```
Google Doc ─▶ Extension (WXT/React) ─▶ FastAPI ─▶ Editorial pipeline ─▶ Scorecard sidebar
             extract via docs export     provider registry      classify → review → judge
                                         + RAG knowledge base    (mock / Claude / GPT / …)
```

## What's built (P1–P6)

- **Extension** — detects Google Docs, extracts text, picks content type + AI model,
  evaluates, renders a liquid-glass scorecard (priority issues, strengths, next steps,
  per-dimension breakdown), light/dark.
- **Any AI provider** — mock (default, no key), **Claude, GPT, Gemini, Grok**, and
  open-source via **Ollama / OpenRouter / Groq / Together / DeepSeek / Mistral**. Keys
  stay on the backend; writers pick from configured providers in the sidebar.
- **Editorial pipeline** — data-driven rubrics per content type, TIES' Editorial DNA,
  single-call or **multi-agent** (per-dimension) modes.
- **Accounts & history** — Google OAuth + dev login, JWT, roles (writer/editor/admin),
  evaluation & document history, user profiles. Async SQLAlchemy (SQLite → Postgres).
- **RAG knowledge base** — handbook, approved/rejected articles, founder notes embedded
  and retrieved into the prompt. Zero-dep hashing embedder → OpenAI; in-memory → Qdrant.
- **Dashboard + admin** — founder/editor analytics and an admin panel (users, rubric
  weights, prompts, knowledge, audit log, AI usage), served at `/dashboard` (no build step).
- **Research integrity (P6)** — claim extraction, unattributed/high-risk-claim and
  citation-gap detection, bias/absolutes/hedges — `POST /api/integrity`.
- **Ops** — Dockerfile, docker-compose (Postgres + Qdrant), GitHub Actions CI,
  Slack/Teams notifications, Sentry hook.

**It runs with zero infrastructure** — SQLite, in-memory vectors, mock provider — and
scales up entirely through environment variables. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Repository layout

```
jalebi/
├── apps/
│   ├── backend/      FastAPI · providers · pipeline · RAG · auth · dashboard · analyzers
│   └── extension/    WXT · React · TypeScript · Tailwind · MV3 side panel
├── docs/ARCHITECTURE.md
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## Quick start

Backend (runs on an empty `.env`):

```bash
cd apps/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
#  API docs → /docs   ·   dashboard → /dashboard   ·   health → /api/health
```

Point it at a real model, e.g. Claude:

```bash
export JALEBI_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-...
```

Extension (needs Node 18+):

```bash
cd apps/extension && npm install && npm run dev
```

Full stack (Postgres + Qdrant):

```bash
docker compose up --build
```

Per-app details in each `README.md`.
