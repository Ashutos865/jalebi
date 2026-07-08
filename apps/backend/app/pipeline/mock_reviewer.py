"""Content-aware mock reviewers.

One function per editorial dimension. Each inspects the real text features and
returns (score, issues, recommendations, summary). This is a stand-in for Claude:
the *shape* of the output is production-final, only the intelligence is heuristic.

Determinism: scores are seeded off a hash of the text, so the same document always
scores the same, and improving the text moves the score. That makes the
"revise → re-evaluate → repeat" loop feel real and keeps tests stable.
"""
from __future__ import annotations

import random
from typing import Callable, Dict, List, Tuple

from app.pipeline.base import PipelineContext
from app.pipeline.text_features import snippet
from app.schemas.evaluation import Issue, Priority

# A reviewer returns (score, issues, recommendations, summary).
ReviewOut = Tuple[int, List[Issue], List[str], str]
Reviewer = Callable[[PipelineContext, random.Random], ReviewOut]


def _clamp(n: float) -> int:
    return max(0, min(100, int(round(n))))


def _jitter(rng: random.Random, spread: int = 3) -> int:
    return rng.randint(-spread, spread)


def _density(count: int, words: int, per: int = 100) -> float:
    """Signals per `per` words — normalizes for document length."""
    return (count / words * per) if words else 0.0


# --- Individual dimension reviewers -----------------------------------------

def review_evidence(ctx: PipelineContext, rng: random.Random) -> ReviewOut:
    f = ctx.features
    cites = f.citation_signal + f.url_count + f.quote_count
    density = _density(cites, f.word_count)
    score = _clamp(55 + density * 12 + min(f.number_count, 10) * 1.5 + _jitter(rng))
    issues: List[Issue] = []
    recs: List[str] = []
    if density < 1.2:
        issues.append(Issue(
            problem="Claims are thinly supported by evidence.",
            explanation="Editorial DNA is evidence-before-opinion, yet few citations, "
                        "figures, or attributed quotes appear in the piece.",
            impact="Readers (and editors) cannot verify the argument; it reads as assertion.",
            suggestion="Attribute each factual claim to a primary source and add supporting data.",
            priority=Priority.high,
            options=[
                "According to [primary source], [restate the claim with a specific figure].",
                "[Attribute this to a named source] reports that …",
                "Add a citation to this claim: “… ([cite source, year]).”",
            ],
        ))
        recs.append("Add at least one primary source per major claim.")
    if f.number_count == 0:
        recs.append("Introduce concrete figures where the argument depends on scale.")
    return score, issues, recs, "Evidence density and attribution across the piece."


def review_research(ctx: PipelineContext, rng: random.Random) -> ReviewOut:
    f = ctx.features
    signal = f.citation_signal + f.url_count + f.context_signal + min(f.number_count, 8)
    score = _clamp(52 + _density(signal, f.word_count) * 9 + f.context_signal * 2 + _jitter(rng))
    issues: List[Issue] = []
    if f.url_count == 0 and f.citation_signal < 2:
        issues.append(Issue(
            problem="No traceable sources.",
            explanation="Strong research references primary sources the reader can follow.",
            impact="The piece cannot be fact-checked and lacks research authority.",
            suggestion="Cite and link the primary sources behind the key claims.",
            priority=Priority.high,
        ))
    return score, issues, [], "Depth of research and use of primary sources."


def review_accuracy(ctx: PipelineContext, rng: random.Random) -> ReviewOut:
    f = ctx.features
    score = _clamp(72 + min(f.citation_signal, 8) * 1.2 + _jitter(rng))
    issues: List[Issue] = []
    if f.number_count >= 3 and f.citation_signal < 2:
        issues.append(Issue(
            problem="Figures are stated without sourcing.",
            explanation="Multiple numbers appear but none are attributed, so their "
                        "accuracy can't be checked.",
            impact="A single wrong figure can discredit the whole piece.",
            suggestion="Attribute every statistic to its source and date.",
            priority=Priority.high,
        ))
    return score, issues, [], "Correctness and internal consistency of facts."


def review_narrative(ctx: PipelineContext, rng: random.Random) -> ReviewOut:
    f = ctx.features
    score = _clamp(60 + min(f.paragraph_count, 8) * 2 + _jitter(rng))
    issues: List[Issue] = []
    recs: List[str] = []
    if f.paragraph_count <= 2 and f.word_count > 250:
        issues.append(Issue(
            problem="The piece reads as one undifferentiated block.",
            explanation="A strong narrative builds in stages; here there is little "
                        "structural progression.",
            impact="The argument is hard to follow and loses the reader.",
            suggestion="Break the piece into a hook, development, and resolution.",
            priority=Priority.medium,
        ))
    if f.word_count < 120:
        recs.append("The piece is short — develop the through-line before publication.")
    return score, issues, recs, "Clarity and progression of the argument."


def review_neutrality(ctx: PipelineContext, rng: random.Random) -> ReviewOut:
    f = ctx.features
    score = _clamp(88 - len(f.sensational_terms) * 9 - len(f.hedges) * 2 + _jitter(rng))
    issues: List[Issue] = []
    if f.sensational_terms:
        term = f.sensational_terms[0]
        issues.append(Issue(
            problem="Sensational language undercuts neutrality.",
            explanation="Editorial DNA forbids sensationalism and clickbait; the copy "
                        f"uses charged wording such as '{term}'.",
            impact="It signals bias and erodes trust in the reporting.",
            suggestion="Replace charged wording with precise, neutral description.",
            priority=Priority.high,
            quote=snippet(ctx.text, term),
            options=[
                f"State what happened plainly, without “{term}”.",
                f"Replace “{term}” with a precise, neutral description of the facts.",
                "Lead with the verifiable fact, not the reaction.",
            ],
        ))
    return score, issues, [], "Neutral, non-sensational, balanced framing."


def review_context(ctx: PipelineContext, rng: random.Random) -> ReviewOut:
    f = ctx.features
    score = _clamp(58 + f.context_signal * 6 + _jitter(rng))
    issues: List[Issue] = []
    if f.context_signal < 2:
        issues.append(Issue(
            problem="Missing historical / strategic / economic context.",
            explanation="TIES pieces situate events in their broader context; little is "
                        "provided here.",
            impact="Readers get the 'what' but not the 'why it matters'.",
            suggestion="Add a short paragraph on the historical or strategic backdrop, "
                       "with an India-first, evidence-based lens.",
            priority=Priority.medium,
        ))
    return score, issues, [], "Historical, strategic, and economic context."


def review_structure(ctx: PipelineContext, rng: random.Random) -> ReviewOut:
    f = ctx.features
    score = _clamp(64 + min(f.paragraph_count, 6) * 3 + (5 if f.headline else -5) + _jitter(rng))
    issues: List[Issue] = []
    if not f.headline:
        issues.append(Issue(
            problem="No clear opening line / headline.",
            explanation="The first line should orient the reader.",
            impact="Weak openings lose readers and editors alike.",
            suggestion="Lead with a specific, informative headline or topic sentence.",
            priority=Priority.medium,
        ))
    return score, issues, [], "Logical flow, introduction, and conclusion."


def review_writing(ctx: PipelineContext, rng: random.Random) -> ReviewOut:
    f = ctx.features
    score = _clamp(80 - len(f.ai_cliches) * 5 - len(f.hedges) * 2 + _jitter(rng))
    issues: List[Issue] = []
    if f.ai_cliches:
        term = f.ai_cliches[0]
        issues.append(Issue(
            problem="Generic AI-style phrasing.",
            explanation=f"Phrases like '{term}' read as filler and violate the "
                        "no-AI-clichés rule.",
            impact="The prose feels generic and lowers editorial quality.",
            suggestion="Cut the cliché and state the point directly.",
            priority=Priority.medium,
            quote=snippet(ctx.text, term),
            options=[
                f"Cut “{term}” and state the point directly.",
                "Replace the filler phrase with a concrete detail.",
                "Say exactly what you mean, without the stock phrase.",
            ],
        ))
    return score, issues, [], "Clarity and freedom from clichés and filler."


def review_readability(ctx: PipelineContext, rng: random.Random) -> ReviewOut:
    f = ctx.features
    penalty = max(0, f.avg_sentence_len - 22) * 1.5 + f.long_sentences * 3
    score = _clamp(90 - penalty + _jitter(rng))
    issues: List[Issue] = []
    if f.long_sentences and f.longest_sentence:
        issues.append(Issue(
            problem="Some sentences are too long to parse easily.",
            explanation=f"{f.long_sentences} sentence(s) exceed 30 words.",
            impact="Long sentences reduce readability and comprehension.",
            suggestion="Split the longest sentences into two.",
            priority=Priority.low,
            quote=(f.longest_sentence[:120] + "…") if f.longest_sentence else None,
        ))
    return score, issues, [], "Sentence and paragraph length for the audience."


def review_grammar(ctx: PipelineContext, rng: random.Random) -> ReviewOut:
    f = ctx.features
    # Heuristic only — real grammar checks arrive with Claude in P2.
    score = _clamp(92 - f.long_sentences * 1.5 - max(0, f.passive_hits - 4) + _jitter(rng, 2))
    recs: List[str] = []
    if f.passive_hits > 5:
        recs.append("Consider converting some passive constructions to active voice.")
    return score, [], recs, "Grammar and mechanics (heuristic pending Claude)."


def review_headline(ctx: PipelineContext, rng: random.Random) -> ReviewOut:
    f = ctx.features
    h = f.headline
    hw = len(h.split())
    score = 70
    issues: List[Issue] = []
    if not h:
        score = 40
        issues.append(Issue(
            problem="No headline detected.",
            explanation="The first line does not read as a headline.",
            impact="Without a headline the piece has no entry point.",
            suggestion="Add a specific, non-sensational headline.",
            priority=Priority.high,
        ))
    else:
        if any(t in h.lower() for t in ("shocking", "you won't", "!!!")):
            score -= 20
            issues.append(Issue(
                problem="Headline is sensational.",
                explanation="Clickbait headlines violate editorial standards.",
                impact="Undermines credibility before the reader begins.",
                suggestion="Rewrite for accuracy and specificity, not shock.",
                priority=Priority.high,
                quote=h,
            ))
        if hw < 4 or hw > 18:
            score -= 8
        if any(ch.isdigit() for ch in h):
            score += 8  # specificity
    return _clamp(score + _jitter(rng)), issues, [], "Headline accuracy and specificity."


def review_citations(ctx: PipelineContext, rng: random.Random) -> ReviewOut:
    f = ctx.features
    score = _clamp(50 + f.url_count * 8 + min(f.citation_signal, 8) * 3 + _jitter(rng))
    issues: List[Issue] = []
    if f.url_count == 0:
        issues.append(Issue(
            problem="No sources are linked.",
            explanation="Prefer primary sources and always attribute factual claims.",
            impact="Claims are unverifiable; the piece isn't citable.",
            suggestion="Link primary sources for each key claim.",
            priority=Priority.high,
        ))
    return score, issues, [], "Attribution and source credibility."


def review_formatting(ctx: PipelineContext, rng: random.Random) -> ReviewOut:
    f = ctx.features
    score = _clamp(85 + (3 if f.paragraph_count > 2 else -8) + _jitter(rng))
    return score, [], [], "Consistent formatting for the medium."


def review_seo(ctx: PipelineContext, rng: random.Random) -> ReviewOut:
    f = ctx.features
    score = _clamp(60 + (10 if f.headline and any(c.isdigit() for c in f.headline) else 0)
                   + min(f.paragraph_count, 6) * 2 + _jitter(rng))
    recs: List[str] = []
    if f.word_count < 300:
        recs.append("Longer pieces tend to rank better; consider expanding key sections.")
    return score, [], recs, "Discoverability and metadata."


def review_engagement(ctx: PipelineContext, rng: random.Random) -> ReviewOut:
    f = ctx.features
    hook_bonus = 8 if (f.headline and len(f.headline.split()) >= 4) else -6
    score = _clamp(66 + hook_bonus - len(f.sensational_terms) * 4 + _jitter(rng))
    issues: List[Issue] = []
    if hook_bonus < 0:
        issues.append(Issue(
            problem="Weak opening hook.",
            explanation="Platform content lives or dies on the first line.",
            impact="A flat opening loses the audience immediately.",
            suggestion="Open with a concrete stake, question, or surprising fact — "
                       "without resorting to clickbait.",
            priority=Priority.medium,
        ))
    return score, issues, [], "Hook and pacing for the platform."


REVIEWERS: Dict[str, Reviewer] = {
    "evidence": review_evidence,
    "research": review_research,
    "accuracy": review_accuracy,
    "narrative": review_narrative,
    "neutrality": review_neutrality,
    "context": review_context,
    "structure": review_structure,
    "writing": review_writing,
    "readability": review_readability,
    "grammar": review_grammar,
    "headline": review_headline,
    "citations": review_citations,
    "formatting": review_formatting,
    "seo": review_seo,
    "engagement": review_engagement,
}
