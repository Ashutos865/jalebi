# Jalebi Extension

Chrome extension (MV3, WXT + React + Tailwind) that evaluates the open Google Doc
against TIES editorial standards and renders a scorecard in the side panel.

## Prerequisites

- Node.js 18+ and npm
- The [backend](../backend) running (default `http://127.0.0.1:8000`)

## Develop

```bash
npm install
npm run dev            # builds to .output/chrome-mv3 and launches a dev browser
```

If you prefer to load it manually: `npm run dev` (or `npm run build`), then in Chrome
go to `chrome://extensions`, enable **Developer mode**, click **Load unpacked**, and
select `apps/extension/.output/chrome-mv3`.

## Use

1. Start the backend (`uvicorn app.main:app --reload` in `apps/backend`).
2. Open any Google Doc.
3. Click the **Jalebi** floating button (bottom-right) or the toolbar icon — the side
   panel opens.
4. Pick the **content type** and (when more than one is configured) the **AI model**,
   then click **Evaluate with Jalebi**.

The **AI model** picker is populated from `GET /api/providers` — it lists only the
providers the backend has keys for (Claude, GPT, Gemini, Grok, or open-source models via
Ollama/OpenRouter/Groq/Together/DeepSeek/Mistral). Keys never leave the backend. The
scorecard footer shows which model scored the piece and how many knowledge-base passages
were used.

The side panel's ⚙ settings let you point at a different backend URL and test the
connection. The default backend is `http://127.0.0.1:8000`; the backend sends permissive
CORS so the panel can reach it. For a hosted backend, set its URL in settings.

## How text extraction works

The content script runs on `docs.google.com` and fetches
`…/document/d/{docId}/export?format=txt` with the user's session — clean plain text,
no DOM scraping, no OAuth. See [../../docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §3.1.

## Layout

```
entrypoints/
  background.ts          opens the side panel
  content.ts             doc extractor + floating action button
  sidepanel/
    index.html · main.tsx · App.tsx · style.css   (React side panel)
components/               Header · Settings · Scorecard · IssueCard · ui primitives
lib/
  api.ts                 backend client (configurable URL)
  doc.ts                 docId parsing + export-endpoint fetch (pure)
  types.ts               mirror of the backend evaluation schema
  score.ts               score → colour bands
  useTheme.ts            light/dark/system
wxt.config.ts            manifest + Tailwind (Vite plugin)
```

## Notes

- Branded toolbar icons are added later; dev builds use Chrome's default icon.
- Component tests (Vitest) land in P2 alongside schema codegen for `lib/types.ts`.
