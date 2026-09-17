# Jalebi — Product & Market Analysis

**What this is:** an assessment of what Jalebi does today, what would have to change for
anyone outside TIES to use it, and where it sits against the tools that already exist.

**Date:** 18 September 2026
**Status:** analysis for a product decision — not a commitment to build

Two parts:

- **Part 1 — For everyone.** Plain language. What the product is, who would buy it,
  what already exists, and what we'd be betting on. No code.
- **Part 2 — For engineers and product.** The generalisation work, with measured
  evidence, file-level scope, and effort.

---
---

# PART 1 — For a non-technical reader

## 1.1 What Jalebi is today

Jalebi reads a draft and answers one question: **is this good enough to publish?**

Not "is the grammar correct" — it scores the piece against an editorial standard, tells
the writer what's weak and why, flags claims that need checking, and tracks the article
through assignment → drafting → review → sign-off.

It currently answers that question **for TIES specifically**. It knows TIES' editorial
constitution, TIES' 300–350 word limit, TIES' 24-hour production loop, and TIES' house
style. That's why it works well for TIES — and why nobody else can use it yet.

## 1.2 The problem with making it public

Here is the issue, measured on the real system rather than assumed.

I took a genuinely good, well-sourced American news article and scored it. Then I changed
nothing except the spelling convention:

| Identical article, different convention | Writing score |
|---|---|
| British spelling, no em dash | **100** |
| American spelling, em dash | **73** |

A correctly written American article is **marked down 27 points** for spelling
"normalized" and using an em dash. That isn't a quality judgement — it's TIES house style
being enforced as though it were universal truth.

The same applies throughout: the 300–350 word limit, the 12-hour drafting deadline, the
"nation-first" editorial rule, the list of approved Indian news sources. All sensible for
TIES. All wrong for a magazine in Berlin or a newsletter in Ohio.

**The good news:** this is mostly *data*, not logic. The machinery — scoring, deadlines,
fact-check surfacing, workflow — is general. It's the settings that are hardcoded.

## 1.3 What's actually out there

I researched the market rather than guessing. Four findings changed how I'd position this.

**The market splits into three groups that don't overlap.**

| What it does | Who does it best | What it's missing |
|---|---|---|
| **Scores against your standards** | Markup AI (formerly Acrolinx) | No workflow, no fact-checking |
| **Manages the workflow** | Kordiam, PublishPress, Contently | No opinion on quality |
| **Surfaces claims to check** | Factiverse, ClaimBuster | No workflow, no standards |

**No product does all three.** That's the gap.

**Grammarly can't express editorial standards.** This surprised me. Grammarly Business
lets you add custom style rules — but a rule is literally *"replace this word with that
word"* ("Acmeco" → "AcmeCo"). You cannot write *"every statistic needs a source"* or
*"don't bury the lead."* The entire category tops out at vocabulary preferences.

**Serious newsrooms are building this themselves.** The BBC built an in-house tool called
"Style Assist" to enforce BBC house style, because nothing off the shelf could. Reuters
built its own governance checkpoints. AP published new AI standards in July 2026 but has
no product that enforces them. **When sophisticated buyers build instead of buying, the
category is missing something.**

**AI detection is collapsing as a trust signal.** Teams currently use AI detectors as a
proxy for "can I trust this draft." They shouldn't. A Stanford study published in
*Patterns* ran 91 essays by non-native English writers through seven commercial
detectors: **61.3% were falsely flagged as AI-written**, and 97.8% were flagged by at
least one detector — while essays by native speakers were classified correctly. Vanderbilt
disabled Turnitin's AI detector, noting that a 1% false-positive rate across their volume
means roughly **750 students wrongly accused per year**. Even GPTZero says its results
should be "a conversation starter, not the final verdict."

This matters for us: **"was this written by AI?" is the wrong question. "Does this meet
our standards?" is the right one** — and nothing on the market answers it.

## 1.4 What a public version would be

**One sentence:** the tool that knows *your* editorial standards, enforces them on every
draft, and won't let a piece reach publication without someone having looked at what it
flagged.

Three things together, which is the part nobody else does:

1. **Your standards, executable.** Not "use shorter sentences" — *your* rubric. Which
   dimensions matter, how much each is worth, what your hard rules are, what your house
   style is. Written once, applied to every draft, with a score you can point at.
2. **Bound to the workflow.** The score isn't a report you read and forget. It's attached
   to the article's state. An editor signing off on something that fails your own checks
   has to record why — and that's visible to whoever runs the desk.
3. **Claims surfaced for a human.** Jalebi never claims to verify facts. It finds every
   statistic and quotation, ranks them by how badly they need checking, and hands an
   editor a worklist. That's deliberate: a tool that claimed to fact-check would be
   trusted, and it would be wrong.

## 1.5 Who would pay

| Segment | Why they'd care | Realistic size |
|---|---|---|
| **Digital newsrooms & independent media** | Standards are the product; small teams, no budget for Contently | 5–50 people |
| **Content agencies** | Must prove quality to clients; freelancers need consistent standards | 10–100 |
| **University journalism programmes** | Teaching editorial judgement, not grammar; detection tools are being disabled | departmental |
| **Regulated-industry content teams** | Need auditable sign-off, currently overpaying enterprise vendors | 10–50 |
| **Think tanks & research orgs** | Sourcing rigour matters more than SEO | 5–30 |

**The pricing gap is real and specific.** Several tools price at roughly $29/month or
$1,000/month with *nothing in between* — and a 10–50 person content team sits exactly in
that hole. A team stitching a credible stack together today spends roughly
**$25,000–110,000/year** across 4–6 tools that don't talk to each other.

## 1.6 What we'd be better at, honestly

**Genuinely differentiated:**

- **Standards you can actually express.** Everyone else tops out at word substitutions.
  Ours can say "every statistic needs a source" because the rules engine already does.
- **Quality bound to workflow.** Nobody joins these. Ours already does — sign-off records
  who overrode what, and why.
- **Fact-check worklist inside the editing loop.** Factiverse and ClaimBuster do claim
  detection but live outside the drafting tool, so nobody uses them under deadline.
- **Explainable scoring.** ~70% of the score comes from deterministic rules, not a model.
  The same text always scores the same, and you can see which rule fired. Editors will
  not trust a number that changes between runs.
- **Runs on nothing.** No API key, no cloud account. That matters to newsrooms with no
  budget and to anyone who can't send drafts to a third party.

**Where we'd lose, and shouldn't pretend otherwise:**

- **Grammarly is better at grammar** and always will be. We should integrate, not compete.
- **Markup AI is the real competitor** — 20 years of enterprise content governance, and it
  genuinely scores against configurable goals. It's enterprise-priced and sales-gated,
  which is the opening, but it isn't a weak incumbent.
- **We have no distribution.** They have millions of users.
- **We can't verify facts**, only surface claims. Say so loudly; the alternative is being
  trusted and wrong.
- **Single-tenant today.** There is no concept of an "organisation" in the system at all.

## 1.7 The honest risks

1. **"Your own rubric" might be too much work for buyers.** Everyone says they want
   custom standards; few will sit down and write one. Mitigation: ship strong presets
   (AP-style newsroom, academic, marketing) so nobody starts from blank.
2. **Markup AI is moving in exactly this direction** — embedding governance agents into
   workflows via API. They may close the gap before we reach it.
3. **Google Docs dependency.** Extraction relies on an export endpoint Google controls.
4. **It's a "should" purchase.** Teams buy things that save time; standards enforcement
   costs time upfront. Needs to be sold as protection against corrections and reputational
   damage, not as efficiency.

## 1.8 What I'd recommend

**Don't build a general "AI writing tool."** That market is saturated, commoditised, and
being absorbed into browsers and operating systems.

**Do build the narrow thing nobody has:** *the editorial standards layer* — your rubric,
enforced, bound to workflow, with claims surfaced.

Sequence:

1. **Make it configurable** (~2–3 weeks). Lift TIES' constants into a config file. Ship
   3–4 presets. This is most of the work and it's mechanical.
2. **Multi-tenant** (~2 weeks). Add organisations. Currently absent entirely.
3. **Onboarding that writes the rubric for you.** The single biggest adoption risk.
4. **Then decide** whether it's a product or an internal tool, based on whether anyone
   outside TIES actually completes step 3.

---
---

# PART 2 — For engineers and product

## 2.0 Current state, measured

| | |
|---|---|
| Backend | ~6,500 lines Python (FastAPI, async SQLAlchemy) |
| Extension | ~5,100 lines TypeScript (WXT, React, MV3) |
| Tests | 249 backend, 56 extension |
| API surface | 36 documented paths |
| Config knobs | 27 env vars — **none for editorial standards** |
| Tenancy | **Single-tenant.** No organisation model exists |

## 2.1 What is TIES-specific, precisely

TIES assumptions appear in 18 files. Categorised by how hard they are to lift:

### Tier 1 — Data, trivially configurable (~1 week)

| What | Where | Problem |
|---|---|---|
| Source tier lists | `constitution.py:270-290` | Indian outlets (RBI, NITI Aayog, The Hindu, Firstpost) hardcoded as credible |
| House style: British spelling | `constitution.py:352`, `rules.py:246` | **Measured: penalises correct US spelling** |
| House style: em dash ban | `rules.py:225-231` | TIES-only preference applied universally |
| Word window 300–350 | `constitution.py:216` | SOP-specific |
| SLA hours 12/18, 10/12 | `workflow/states.py:75-78` | SOP-specific |
| AI/plagiarism caps 20%/15% | `constitution.py:166-167` | SOP-specific |
| Dimension weights | `constitution.py:62-67` | Already admin-editable ✓ |

**Evidence this matters** — identical content, two conventions:

```
US style (normalized, labor, em dash)   overall=74  writing=73
UK style (normalised, labour, comma)    overall=76  writing=100
```

A 27-point writing penalty for correct American English. Any US customer hits this
immediately.

### Tier 2 — Structure, moderate work (~1–2 weeks)

| What | Where | Problem |
|---|---|---|
| SOP header block | `sop_header.py` (207 lines) | Parses 9 fixed TIES field names |
| Nation-first review | `nation_first.py` (162 lines) | Wholly India-specific concept |
| Workflow states | `workflow/states.py` | TIES' loop; others differ |
| Content types | `schemas/evaluation.py` | 17 types incl. TIES categories |

`sop_header.py` should become a **configurable metadata schema** — the parsing logic is
general, the field names are not. `nation_first.py` should generalise to
**"editorial red lines"**: an org defines subjects requiring extra sourcing scrutiny. The
mechanism (unsourced disparagement of a protected subject → flag for human review, never
a score penalty) is sound and reusable; only the subject list is India-specific.

### Tier 3 — Genuinely general, no work needed

These already work for anyone: `engine.py` (blending, caps, bands), `factcheck.py` (claim
extraction and ranking), `grammar/` (LanguageTool + heuristics), the RAG knowledge base,
auth/RBAC, the production-loop state machine *mechanism*, and the extension.

## 2.2 Competitive positioning — verified

Sources were checked; uncertainty is flagged rather than smoothed over.

### The three-way split (verified)

**Standards scoring — Markup AI (formerly Acrolinx).** Rebrand confirmed at
[markup.ai](https://markup.ai/lets-talk-acrolinx-to-markup-ai/): *"Acrolinx is now Markup
AI... For over 20 years, Acrolinx has been the enterprise solution for content
governance."* Sells "Content Guardian Agents" as "the confidence layer between writing and
publishing." **This is the real competitor.** Enterprise-priced, sales-gated, custom
guidelines require vendor support. No workflow; no fact-checking.

**Workflow — Kordiam** (newsroom planning, sales-led), **PublishPress Checklists**
($49–$199, WordPress-only, binary gates not scored quality), **Contently** (workflow +
style-guide enforcement + e-signed compliance approvals; opaque enterprise pricing).

**Fact-check — Factiverse** (claim + stance detection, 114 languages, demo-gated;
publishes no independent accuracy figures), **ClaimBuster** (free academic API; detects
check-worthy claims, does not verify them).

### The rubric expressiveness ceiling (verified, and the core insight)

Grammarly's custom style rule primitive is literally `original text → rule text →
explanation` — word and phrase substitution only
([Grammarly Support](https://support.grammarly.com/hc/en-us/articles/360043832652-Create-style-rules)).
Tier caps: Pro 1 rule set, Business up to 50, Enterprise unlimited.

**No shipping product can encode:** "every contested claim is attributed," "the nut graf
appears by paragraph three," "no single-source stories on contested topics." Jalebi's
rules engine already expresses this class of rule.

### Market changes that invalidate older assumptions

- **Grammarly's parent renamed to Superhuman** (Oct 2025); the writing product keeps its
  name.
- **Microsoft Editor is effectively dead** — browser extensions retired Oct 2025, free
  Office Copilot discontinued April 2026. Not a competitor.
- **Writesonic pivoted to AI-search visibility/GEO**; no longer a writing-quality tool.
- **ClearVoice's pricing URL now redirects to Fiverr** — likely being absorbed.

### AI detection: why we should not build it

| Product | Claimed FPR | Independently measured |
|---|---|---|
| Originality.ai | 0.5% | ~5.7% |
| Copyleaks | ~0.2% | 7.2–12% |
| Winston AI | 99.98% accuracy | 76–92% |
| Turnitin | <1% doc-level | Vanderbilt: ~750 papers/yr wrongly flagged |

**Citation-grade:** Liang et al., *Patterns* (Cell Press) 2023 — seven commercial
detectors on 91 non-native TOEFL essays: **61.3% average false-positive rate**, **97.8%
flagged by at least one detector**, while native-speaker essays were classified
correctly. Mechanism: low perplexity in non-native writing. Verified via the published
paper ([PubMed](https://pubmed.ncbi.nlm.nih.gov/37521038/) ·
[arXiv](https://arxiv.org/abs/2304.02819)).

**Product implication:** keep recording AI/plagiarism percentages from the editor's own
tooling (as built) and never estimate them in-product. This is both correct and a
positioning advantage while the category loses legitimacy.

### Pricing context

Verified official (USD): Jasper Pro $59/mo annual (1 seat); Copy.ai Chat $29/mo then
**Growth $1,000/mo**; Writesonic Starter $79/mo (1 user); Anyword Starter $39/mo annual;
Originality.ai Pro $12.95/mo annual; Ghost Publisher $29/mo (3 staff); Notion Business
$20/member/mo; PublishPress Checklists $49–$199.

**The gap:** Copy.ai jumps $29 → $1,000/mo with nothing between — precisely the 10–50
person band. Realistic current spend for such a team: **~$25,000–110,000/yr** across 4–6
disconnected tools.

*Pricing caveat: vendor pages geolocated to INR for Grammarly and ProWritingAid, so USD
figures for those are secondary. Sales-gated vendors (Markup AI, Contently, Skyword,
Kordiam, Factiverse, Turnitin) have no verifiable public pricing.*

## 2.3 The generalisation plan

### Phase A — Configurable standards (~2–3 weeks)

Replace the TIES constants with a loadable profile:

```yaml
# standards/newsroom-us.yaml
house_style:
  spelling: us            # us | uk | off
  em_dash: allowed        # allowed | discouraged | forbidden
dimensions:
  accuracy:  { weight: 0.30, alpha: 0.75 }
  insight:   { weight: 0.20, alpha: 0.15 }
hard_caps:
  fabricated_quote: 0
  unsupported_claim: 50
content_types:
  news_article: { word_min: 400, word_max: 800 }
sources:
  tier_1: [reuters, associated press, "federal reserve", ...]
workflow:
  drafting_hours:  { target: 24, limit: 48 }
  editing_hours:   { target: 12, limit: 24 }
integrity:
  max_ai_percent: 20
  max_plagiarism_percent: 15
```

**Ship presets:** `ties`, `newsroom-us`, `newsroom-uk`, `academic`, `marketing`. Nobody
should start from blank — that's the adoption risk.

Work: `constitution.py` becomes a loader; `rules.py` reads house-style flags instead of
assuming; `states.py` takes hours from config; `sop_header.py` takes field names from
config; `nation_first.py` generalises to configurable red-line subjects.

**Regression risk is low and testable:** the 249-test suite pins current behaviour, and
the `ties` preset must reproduce today's scores exactly. That's the acceptance criterion.

### Phase B — Multi-tenancy (~2 weeks)

Add `Organisation`; `organisation_id` on User, Document, Evaluation, KnowledgeDoc,
RubricOverride; scope every query; per-org standards profile and knowledge base. This is
currently **entirely absent** and is the hard prerequisite for any hosted offering.

### Phase C — Onboarding (~2 weeks)

The make-or-break piece. "Upload your style guide" → parse into a draft profile → let an
editor confirm each rule. Without this, "bring your own rubric" is a blank page and
nobody completes it.

### Phase D — Integrations

Slack/Teams (webhook exists), WordPress/Ghost publish gate, Google Docs API for
formatting checks (currently impossible from plain-text export).

## 2.4 What not to build

- **AI detection** — §2.2. Record, never estimate.
- **Content generation** — saturated; different buyer; conflicts with being the impartial
  check on writing.
- **A grammar engine** — LanguageTool already integrated; Grammarly wins this.
- **A CMS** — integrate with Ghost/WordPress instead.

## 2.5 Open questions

1. **Is "bring your own rubric" a feature or a barrier?** Everything hinges on this. Test
   with 3–5 external editors before Phase A.
2. **Hosted or self-hosted?** Self-hosting suits privacy-sensitive newsrooms and avoids
   Phase B; hosting is the only path to a real business.
3. **Does TIES remain a tenant or a fork?** A preset keeps one codebase; a fork lets TIES
   move faster.
4. **What does the fact-check worklist do about `<all_urls>`?** The inline checker's
   privacy posture is acceptable internally; a public product needs a stronger story.

## 2.6 Verification note

Claims in this document were checked rather than recalled. The Acrolinx→Markup AI rebrand
and the Stanford detector-bias figures were verified against primary sources. Pricing
marked "verified official" came from vendor pages; sales-gated vendors have none.
Two names in the original research brief — "Welder" and "Newsroom AI" — could not be
confirmed as existing editorial products and are excluded.
