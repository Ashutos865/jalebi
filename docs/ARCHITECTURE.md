# Jalebi — Architecture

This document captures the decisions behind Jalebi and is updated as the system
evolves. It is deliberately lean: it records *why* things are the way they are, so
future contributors don't re-lit­igate settled choices.

---

## 1. What Jalebi is

An editorial quality-assurance system. It behaves like a Senior Managing Editor:
it evaluates content against TIES' editorial standards, explains weaknesses,
recommends fixes, and rules on publication readiness. It **coaches**, it does not
rewrite.

Scale target: ~100 internal users. This is an organizational tool, so we optimize
for **maintainability, editorial quality, and modularity** — not for
hyperscale distributed infrastructure.

---

## 2. System shape

```
┌──────────────────────────┐        HTTPS/JSON         ┌────────────────────────────┐
│  Chrome Extension (MV3)   │  ───────────────────────▶ │  FastAPI backend           │
│  WXT · React · Tailwind   │   POST /api/evaluate      │                            │
│                           │                           │  ┌──────────────────────┐  │
│  content script:          │                           │  │ Editorial Pipeline   │  │
│   detect Google Doc       │   ◀───────────────────────│  │  1 classify          │  │
│   extract text            │   EvaluationResult JSON   │  │  2 review dimensions │  │
│  side panel (React):      │                           │  │  3 judge readiness   │  │
│   Evaluate → scorecard    │                           │  └──────────┬───────────┘  │
└──────────────────────────┘                           │             │              │
                                                        │      ┌──────▼───────┐      │
                                                        │      │ Evaluator     │     │
                                                        │      │  Mock (now)   │     │
                                                        │      │  Claude (P2)  │     │
                                                        │      └──────────────┘      │
                                                        └────────────────────────────┘
```

---

## 3. Key decisions (with rationale)

### 3.1 Google Docs text extraction — export endpoint, not DOM scraping
Modern Google Docs renders the document to `<canvas>`, so the text is **not in the
DOM** and cannot be reliably scraped. The two viable options are:

- **Annotated Canvas API** — how Grammarly/LanguageTool draw inline underlines.
  Requires an explicit whitelist grant from Google. Out of our control; rejected for v1.
- **Export endpoint** — `https://docs.google.com/document/d/{docId}/export?format=txt`.
  A content script running on `docs.google.com` fetches this **with the user's
  existing session cookies** (same-origin) and receives clean plain text. No OAuth
  consent screen, no whitelist. **Chosen for v1.**

Consequence: Jalebi feedback lives in the **sidebar and quotes the passages it
refers to**, rather than drawing marks inside the document. This is the right
trade for an internal tool and removes a dependency we cannot influence.

Upgrade path (P3): Google Docs API + OAuth for structured extraction (tabs,
headings, comments) and to support docs the export path can't reach.

### 3.2 Extension framework — WXT
Vite-based, fastest HMR, first-class MV3 + side panel + React, not locked to a
bundler. 2025 consensus favors it over Plasmo/CRXJS for new builds.

### 3.3 Backend — FastAPI
Typed (Pydantic) request/response, async, OpenAPI docs for free, natural fit for
AI orchestration and streaming later.

### 3.4 Evaluation is a pipeline, not a prompt
Editorial review is decomposed into stages — **classify → review each dimension →
judge readiness** — each with a focused responsibility and structured output. This
is more consistent and transparent than one monolithic prompt, and it upgrades to
LangGraph-style multi-agent orchestration (P5) without changing the API contract.

### 3.5 Mock first, Claude behind an interface
`Evaluator` is an abstract interface. `MockEvaluator` (P1) produces realistic,
**content-aware** feedback by analyzing real text features (citations, headline,
readability, AI clichés, sensationalism, hedging). `ClaudeEvaluator` (P2) implements
the same interface. The API, schema, and UI never learn which one ran.

### 3.6 Content type is writer-selected in v1
The writer picks the content type (News Article, Policy Analysis, …) in the sidebar;
each type maps to a **rubric** (a weighted set of editorial dimensions). An automatic
content-type classifier stage is added in P2.

---

## 4. The evaluation contract

The Pydantic models in `apps/backend/app/schemas/evaluation.py` are the **single
source of truth**. The extension's `lib/types.ts` mirrors them by hand today; P2
introduces schema codegen so they can never drift.

Shape (abridged):

```jsonc
{
  "overall_score": 91,
  "publication_ready": false,
  "publication_readiness": "Needs Minor Revision",
  "content_type": "news_article",
  "summary": "...",
  "categories": [
    { "name": "Research", "score": 95, "weight": 0.2,
      "issues": [ { "problem": "...", "explanation": "...", "impact": "...",
                    "suggestion": "...", "priority": "high",
                    "example": "...", "quote": "..." } ],
      "recommendations": ["..."] }
  ],
  "critical_issues": [ /* highest-priority issues, surfaced first */ ],
  "strengths": ["..."],
  "next_steps": ["..."],
  "meta": { "evaluator": "mock", "schema_version": "1.0", "duration_ms": 42 }
}
```

Every issue carries **Problem · Explanation · Impact · Suggestion · Priority ·
Example · Quote**, per the editorial spec — feedback is always actionable and
references the actual content.

---

## 5. Rubrics & Editorial DNA

Rubrics are **data**, not code (`app/rubrics/`). A rubric is a content type plus a
list of weighted `Dimension`s (Research, Evidence, Narrative, Neutrality, Structure,
Writing, Grammar, Headline, Citations, …). Editorial DNA (evidence before opinion,
no sensationalism, provide historical/strategic/economic context, India-first but
evidence-based, no AI clichés) is encoded as reviewer heuristics now and as prompt
guidance for Claude in P2.

---

## 6. Roadmap — all phases implemented

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **P1** | Extension ↔ backend ↔ mock pipeline ↔ scorecard sidebar | ✅ |
| **P2** | **Any AI provider** behind `Evaluator` — Claude, GPT, Gemini, Grok + Ollama/OpenRouter/Groq/Together/DeepSeek/Mistral (open source); provider **registry**; `/api/providers`; per-request override; **multi-agent** pipeline (`JALEBI_PIPELINE=multi`) | ✅ |
| **P3** | Async SQLAlchemy (SQLite→Postgres); Google OAuth + dev-login + JWT + roles; evaluation & document history; user profiles | ✅ |
| **P4** | RAG knowledge base — hashing embedder (zero-dep) or OpenAI; in-memory store or Qdrant; retrieval folded into the prompt; ingest/search API | ✅ |
| **P5** | Multi-agent pipeline; founder/editor **dashboard** + **admin panel** (users, rubric weights, prompts, knowledge, audit log, AI usage); analytics | ✅ |
| **P6** | Research-integrity analyzers (claim extraction, unattributed/high-risk claims, citation gaps, bias/absolutes/hedges); Slack/Teams notifications; Sentry hook | ✅ |

Everything degrades to a **zero-infra local default** — SQLite, in-memory vector
store, mock provider, hashing embeddings — so `uvicorn app.main:app` runs on an empty
`.env`. Production swaps each piece via env (Postgres, Qdrant, provider keys, OpenAI
embeddings) with no code change.

### API surface

| Method | Path | Role | Purpose |
|--------|------|------|---------|
| GET | `/api/health`, `/api/providers`, `/api/content-types` | — | status / catalogues |
| POST | `/api/evaluate` | optional | run pipeline; `provider` override; persists history |
| POST | `/api/classify` | optional | auto-detect content type |
| POST | `/api/check` | optional | real-time grammar/style (inline extension) |
| POST | `/api/integrity` | optional | claim/citation/bias analysis (P6) |
| POST | `/api/auth/dev-login`; GET `/api/auth/google/*`, `/api/auth/me` | — / user | auth |
| GET | `/api/evaluations`, `/api/evaluations/{id}` | user | history (own; all for editor+) |
| GET/POST/DELETE | `/api/knowledge*` | editor/admin | knowledge base |
| GET | `/api/analytics/overview` | editor+ | dashboard metrics |
| — | `/api/admin/*` | admin | users, rubric overrides, prompts, logs, usage |
| GET | `/dashboard` | API-auth'd | server-rendered founder/editor + admin UI |

### Deployment

- **Local:** `uvicorn app.main:app --reload` (SQLite + mock).
- **Container:** `apps/backend/Dockerfile`; `docker compose up` → backend + Postgres + Qdrant.
- **PaaS:** image respects `$PORT` (Railway/Render); set DB URL, JWT secret, admin emails, keys.
- **CI:** `.github/workflows/ci.yml` runs backend `pytest` + extension type-check/build.
- **Migrations:** Alembic (`migrations/`, async env). Dev auto-creates tables
  (`JALEBI_AUTO_CREATE=true`); prod sets it false and runs `alembic upgrade head`
  (the Dockerfile does this before serving).

## 6c. Inline, web-wide grammar layer

Beyond the Google-Docs sidebar (whole-document editorial evaluation), Jalebi has a
**real-time inline checker** that works in any editable field on any site:

- **Extension:** a second content script (`entrypoints/inline.content.ts`, matches
  `<all_urls>`, excludes the Docs canvas) attaches to a focused `<textarea>`,
  `<input>`, or `contenteditable`, debounces typing, and draws underlines with a
  one-click-fix popover. Rects are computed via a mirror technique (inputs) or native
  `Range` (contenteditable); requests proxy through the background worker to bypass
  page CSP.
- **Engine:** `POST /api/check`. The checker is **LanguageTool** (mature open-source,
  thousands of rules) when `JALEBI_LANGUAGETOOL_URL` is set (docker-compose ships the
  service), else a dependency-free heuristic checker (typos, repeats, spacing,
  capitalization, a/an). This is the answer to "correction precision depends on the
  LLM" — a specialized engine, not the LLM.

**Honest boundary:** Google Docs' canvas rendering blocks inline underlines *inside
the doc* without Google's Annotated-Canvas whitelist, so Docs stays sidebar-only; the
inline layer covers the rest of the web (Gmail, LinkedIn, X, CMS, Notion, …).

## 7. Testing & quality

- Backend: `pytest` over the pipeline and API — deterministic because the mock
  seeds off a content hash (same text → same score; improved text → changed score).
- Extension: component tests (Vitest) added in P2; doc-extractor kept pure and unit-testable.
- Types are the contract; both ends are fully typed.

## 8. Security posture (built up over phases)

API keys live only on the backend (never in the extension). P3 adds JWT + Google
OAuth, role-based access (writer / editor / admin), audit logging, input validation,
and rate limiting. Transport is HTTPS in every hosted environment.
