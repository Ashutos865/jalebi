# TIES Editorial Standards (AI Editor Specification)

This is the constitution the Jalebi editor grades against. It is written so that a
reader with zero prior context understands exactly how TIES thinks, edits, and
publishes. The machine-readable weights, caps, and phrase lists live in
`app/scoring/constitution.py`; this document is the human-readable source of truth
and is also seeded into the knowledge base.

## Philosophy

TIES is a research-first publication that exists to help readers understand the
world more deeply. Our objective is not to be first, not to be sensational, and not
to produce the highest volume of content. Our objective is to publish pieces that
change how readers think about a subject by presenting accurate information,
rigorous research, and original insight.

Every published piece should leave the reader with at least one genuinely new
perspective. The editorial system optimises for **accuracy, depth, originality, and
long-term credibility**, even if that occasionally reduces virality.

## A. Meaning of the Score

The score represents **how close a piece is to being publishable under the TIES
editorial standard** — not grammar or readability alone. It answers one question:

> Would publishing this article strengthen or weaken TIES' reputation as a
> research-first publication?

### Bands
- **90–100** Immediately publishable. Factually reliable, well researched, logically
  structured, genuinely insightful. The reader leaves with a perspective they did
  not have before.
- **80–89** Strong; needs only minor refinement (transitions, sourcing, framing, wording).
- **70–79** Good foundation but lacks sufficient depth, originality, evidence, or
  narrative quality. Needs meaningful editing.
- **60–69** Competent but ordinary. Reads like a standard AI-generated or average
  online article. Should not be published.
- **Below 60** Fails editorial standards: factual weakness, unsupported claims, poor
  structure, weak sourcing, misleading framing, or reputational risk.

**Publication threshold: only articles scoring 85 or above are normally approved.**

### Calibration anchors
- **~90** Begins with a simple observation, uncovers a hidden mechanism, supports
  every claim with evidence, and changes how the reader thinks about the subject.
- **~70** Accurately summarises facts and statistics but offers little original
  analysis beyond what already exists.
- **~50** A generic list of facts with little structure, weak sourcing, no original
  thinking, and no meaningful takeaway.

## B. Editorial Dimensions (weights)

1. **Research Accuracy — 30%.** Every factual statement must be accurate. Accuracy
   is the foundation of credibility.
2. **Original Insight — 20%.** The piece must reveal a new way of understanding a
   topic, not merely inform. The reader should feel "I never thought of it like that."
3. **Narrative Structure — 15%.** Each paragraph creates curiosity for the next; the
   ending feels earned.
4. **Depth — 10%.** Explore systems, incentives, history, economics, or psychology
   rather than stopping where typical articles stop.
5. **Credibility & Sourcing — 10%.** Important claims require attribution. Weak
   sourcing reduces credibility regardless of writing quality.
6. **Writing Quality — 10%.** Natural and human; varied sentence rhythm; flowing
   paragraphs; no robotic patterns.
7. **Headline — 5%.** Attracts attention without exaggerating what the article proves.

### Weight adjustments by content type
- **Breaking News** — Accuracy 40, Sourcing 20, Insight 10 (remainder across the rest).
- **Opinion** — Insight 30, Accuracy 25.
- **Analysis** — Accuracy 25, Insight 25, Structure 20.
- **Investigative** — Accuracy 40, Sourcing 20, Insight 15.

## C. Hard Rules (override all scoring — the score is capped at the value shown)
- Unsupported factual claim → **max 50**
- Major factual error → **max 40**
- Fabricated statistic → **max 20**
- Fabricated quotation → **automatic rejection (0)**
- Sensitive allegation without a primary official source, two independent credible
  sources, or direct documentary evidence → **max 45**
- Opinion presented as fact → **max 65**
- Headline unsupported by the article → **max 70**
- Clickbait → penalty

## D. Factuality & Sourcing

Source hierarchy:
- **Tier 1** Government publications, court judgments, legislation, official
  statistics, peer-reviewed journals, primary company filings.
- **Tier 2** Reuters, AP, AFP, Bloomberg, PTI.
- **Tier 3** Established newspapers, academic institutions, recognised think tanks.
- **Tier 4** Named experts, industry reports.
- **Tier 5** Blogs, opinion articles.
- **Tier 6** Social media — never sufficient by itself.

Every numerical claim should include attribution. Claims that cannot be verified
should never receive positive credit; they should be flagged.

## E. Neutrality & Bias

Neutrality means evidence leads conclusions; conclusions do not dictate evidence.
Flag unsupported absolutist phrasing: *obviously, clearly, everyone knows,
undeniably, without question, always, never*. Emotion is acceptable; manipulation is
not — strong language must be proportional to evidence. High-scrutiny topics:
politics, religion, war, ethnicity, historical disputes, individual allegations,
medical claims, scientific claims.

## F. Structure
- **News** — Headline, Lead, Context, Evidence, Implications.
- **Opinion** — Observation, Evidence, Analysis, Reflection.
- **Investigative** — Question, Evidence, Evidence, Evidence, Open conclusion.

Headlines never promise more than the article proves; avoid misleading curiosity
gaps and clickbait.

## G. House Style

Voice: curious, measured, research-driven, intellectually confident, observational,
clear, elegant. Avoid corporate jargon, motivational writing, generic AI phrasing,
professor-like lecturing, and needlessly emotional language.

Language: **British English.** Long flowing paragraphs are preferred over
fragmented one-line writing. Avoid excessive bullet lists. **No em dash.** Use
precise vocabulary rather than dramatic vocabulary.

AI clichés to penalise: "in today's fast-paced world", "it is worth noting", "this
highlights", "this underscores", "the bottom line", "in conclusion", "one thing is
clear", "as we move forward", "needless to say", "now more than ever", "let's dive in".

## H. Explainability

Every evaluation must explain: the final score, the score for each dimension, hard-rule
violations, the publication recommendation, required revisions, major strengths, and
major weaknesses. The editor must never return only a number — it must explain why.

## Editorial Principle

The single most important question before approving any article:

> After reading this, does the reader understand the world better than they did five
> minutes ago?

If the answer is no, the article should not be published, however well written.

## Determinism & method

Identical content must produce an identical score every time. Evaluation is a hybrid:
**~70% deterministic rules** (fact-flagging, sourcing, structure, style, headline
alignment, hard caps) and **~30% AI judgment** (originality, insight, narrative,
intellectual value). The AI primarily detects and justifies issues; it does not
arbitrarily assign the number.
