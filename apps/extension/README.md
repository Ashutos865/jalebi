# Jalebi extension

Chrome MV3 extension: a side panel for editorial review inside Google Docs, plus an
inline grammar layer for the rest of the web. Built with WXT, React and Tailwind.

## Develop

```bash
npm install
npm run dev            # HMR, loads an unpacked build
npm run compile        # tsc --noEmit
npm test               # 60 tests (vitest + jsdom)
npm run build          # .output/chrome-mv3
npm run zip            # store package
```

Load `.output/chrome-mv3` at `chrome://extensions` with Developer mode on. Point the
panel at your backend in Settings; the default is `http://127.0.0.1:8000`.

## What it does

**Side panel** (Google Docs). Extracts the document, runs an evaluation, and shows the
score, SOP compliance, production-loop state and a review workspace where fixes can be
applied to a local copy and copied back.

**Inline checker** (all sites). Attaches to a focused editable field, debounces typing,
and underlines issues with a one-click fix. Password fields, payment details and
one-time codes are never read — see `lib/inline/editable.ts`.

## Layout

```
entrypoints/
  sidepanel/App.tsx     panel shell: phases, doc loading, evaluation
  content.ts            Google Docs detection + text extraction
  inline.content.ts     inline checker host (all sites)
  background.ts         service worker: backend proxy, side-panel behaviour

components/
  Scorecard.tsx         score, summary, strengths, next steps, breakdown
  ReviewCanvas.tsx      mirrored document with inline highlights and fixes
  SopPanel.tsx          SOP compliance checklist
  WorkflowPanel.tsx     production loop: stage, SLA, role-appropriate actions
  Settings.tsx          backend URL, sign-in, inline toggle
  icons.tsx             the icon set — inline SVG, currentColor, no emoji
  vitals.tsx            score hero, gradient bars, section pills
  controls.tsx          buttons, toggles, pills, meters

lib/
  api.ts                backend client; normalises FastAPI error shapes
  doc.ts / docs.ts      Docs extraction and the Docs/Drive API layer
  types.ts              mirrors the backend Pydantic schemas
  inline/               checker, editable-field abstraction, overlay, rects
```

## Design notes

**No emoji.** The interface uses a stroke-based inline SVG icon set. Coloured emoji
read as decoration, and this is a tool for deciding whether something is fit to
publish. Line icons also inherit `currentColor`, so they adapt to light/dark and to
each section's accent.

**Two type stacks.** A transitional serif for prose — summaries, strengths, issue
explanations — and a UI sans for controls and labels. Setting everything in a serif
looks better in a screenshot and is worse to use: at 11–12px serifs blur and dense
labels lose legibility. Both are system fonts, so nothing is downloaded.

**Colour carries meaning.** `scoreColour()` maps a score to the Constitution's bands,
and every ring, bar and wash uses it. Green always means ready.

**Text edits are applied by index, never by pattern.** `String.replace(quote, fix)`
rewrites the *first* match rather than the highlighted one, and interprets `$&`/`$1`
in the replacement — a model returning `$1,000` corrupted the output. See
`replaceMark()` in `ReviewCanvas.tsx`.

**Tests run under jsdom.** The DOM-driven modules carry the highest user-facing risk —
the inline checker writes into the user's live text — so they are tested rather than
only the pure helpers.

## Known limitation

The inline checker declares `<all_urls>` host access. Field-level filters mean it never
reads credentials or payment data, but broad host access is the main obstacle to a
public Chrome Web Store listing. See [../../PRODUCT.md](../../PRODUCT.md) §2.1.
