# Jalebi

**An editorial quality-assurance system.**

Jalebi is not a grammar checker. It reads a draft and answers one question: *is this
good enough to publish?* It scores the piece against an editorial standard, explains
what is weak and why, surfaces the claims that need checking, and tracks the article
from assignment to sign-off.

It ships as a Chrome extension that works inside Google Docs, backed by a FastAPI
service.

```
Google Doc ─▶ Extension (WXT/React) ─▶ FastAPI ─▶ Scoring engine ─▶ Sidebar
             text via the export API      rules (72%) + AI judgment (28%)
```

## What it does

**Scores against an editorial standard.** Seven weighted dimensions — accuracy,
insight, narrative, depth, sourcing, writing, headline — with hard caps for things no
score should survive (a fabricated quotation caps the result at 0). Weights are
tunable per content type from the admin panel, and the change takes effect on the next
evaluation.

**Works with no API key.** About 72% of the score comes from a deterministic rules
engine: source tiers, attribution, statistics without sources, reasoning structure,
house style. The same text always scores the same. An AI provider adds judgment on top
of that, but nothing depends on one being configured.

**Surfaces claims rather than verifying them.** `POST /api/factcheck` returns every
checkable claim with the citation nearest it, ranked by how badly it needs review.
Jalebi does not fetch URLs or decide whether a source supports a claim — that is the
editor's job, and a tool that pretended otherwise would be trusted and wrong.

**Runs the production loop.** Assignment, drafting, review, revision, sign-off, with
the deadline windows the newsroom's own SOP defines. Editors approve from the sidebar;
approving a piece that fails its checks records a written reason.

**Checks grammar inline, anywhere.** A second content script attaches to editable
fields on any site and underlines issues via LanguageTool, or a dependency-free
heuristic checker when no LanguageTool server is configured. Password fields, payment
details and one-time codes are never read.

**Records integrity results, never guesses them.** AI-content and plagiarism
percentages come from the editor's own tooling. Jalebi stores them, applies the
thresholds and gates sign-off. It does not run AI detection — see
[PRODUCT.md](PRODUCT.md) for the evidence behind that decision.

## Quick start

The backend runs on an empty `.env` — SQLite, in-memory vectors, no API key:

```bash
cd apps/backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
#  API docs → /docs   ·   dashboard → /dashboard   ·   health → /api/health
```

Point it at a model when you want AI judgment as well as rules:

```bash
export JALEBI_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-...
```

The extension (Node 18+):

```bash
cd apps/extension
npm install
npm run build
```

Then load `apps/extension/.output/chrome-mv3` at `chrome://extensions` with Developer
mode on. Open a Google Doc and click the Jalebi icon.

Full stack with Postgres, Qdrant and LanguageTool:

```bash
docker compose up --build
```

## Layout

```
jalebi/
├── apps/
│   ├── backend/          FastAPI · scoring · workflow · RAG · auth · dashboard
│   │   ├── app/scoring/    rules, reasoning, constitution, SOP compliance
│   │   ├── app/analysis/   fact-check worklist, integrity, editorial red lines
│   │   ├── app/workflow/   production-loop state machine
│   │   └── app/text/       shared text utilities
│   └── extension/        WXT · React · TypeScript · MV3 side panel
└── docs/
    ├── ARCHITECTURE.md     how it works and why
    ├── CONFIGURATION.md    every environment variable
    └── DEPLOYMENT.md       running it in production
```

## Documentation

| Document | What it covers |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System shape, scoring model, design decisions |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Every environment variable and its effect |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production setup, including the startup safety gate |
| [PRODUCT.md](PRODUCT.md) | Market analysis and what a public version would require |
| [PLAN.md](PLAN.md) | The hardening work, with measured findings |
| [SOP_IMPLEMENTATION.md](SOP_IMPLEMENTATION.md) | How the TIES Content SOP maps onto the system |

## Tests

```bash
cd apps/backend  && pytest -q          # 349 tests
cd apps/extension && npm test          # 60 tests
```

No API key is required for either: the test suite pins `JALEBI_PROVIDER=mock`, so
results are deterministic and cost nothing. No test makes a live provider call.

## Status

Built for TIES and configured to its editorial standard. The scoring mechanisms are
general but the constants are not — house style, word windows, deadline windows and
source lists are TIES-specific, so another newsroom would need the configuration work
described in [PRODUCT.md](PRODUCT.md) §2.3 before using it.
