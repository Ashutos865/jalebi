"""Deterministic rules engine — the reproducible ~70% of the score.

Pure functions over the article text. No model, no randomness: the same input
always yields the same RuleReport. Every check maps to a clause of the Editorial
Constitution. Produces per-dimension rule scores (0-100), triggered hard caps,
concrete issues, and an explainable pass/fail checklist.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.scoring import constitution as C


# ── result types ─────────────────────────────────────────────────────────────
@dataclass
class RuleIssue:
    dim: str
    problem: str
    explanation: str
    impact: str
    suggestion: str
    priority: str = "medium"  # critical | high | medium | low
    quote: Optional[str] = None


@dataclass
class CapHit:
    code: str
    ceiling: int
    label: str
    quote: str


@dataclass
class CheckItem:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class RuleReport:
    dim_scores: Dict[str, int]
    caps: List[CapHit] = field(default_factory=list)
    issues: List[RuleIssue] = field(default_factory=list)
    checklist: List[CheckItem] = field(default_factory=list)
    signals: Dict[str, int] = field(default_factory=dict)


# ── text helpers ─────────────────────────────────────────────────────────────
_SENT = re.compile(r"[^.!?\n]+[.!?]?", re.MULTILINE)
_WORD = re.compile(r"[A-Za-z']+")
# "hard" statistics: percentages, currency, large counts, explicit magnitudes.
_STAT = re.compile(
    r"(\$\s?\d[\d,]*|\d[\d,]*\s?(?:%|percent|per cent)|\b\d[\d,]*\s?"
    r"(?:million|billion|trillion|crore|lakh|thousand|people|deaths|casualties|"
    r"soldiers|km|kg|tonnes|votes|seats)\b|\b\d{4}\b(?=.*\b(?:since|in|by)\b))",
    re.IGNORECASE,
)


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENT.findall(text) if s.strip()]


def _paragraphs(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _count_ci(text_low: str, phrase: str) -> int:
    return text_low.count(phrase)


def _has_attribution(sentence_low: str) -> bool:
    if any(m in sentence_low for m in C.ATTRIBUTION_MARKERS):
        return True
    for tier_terms in C.SOURCE_TIERS.values():
        if any(t in sentence_low for t in tier_terms):
            return True
    return False


def _clip(v: float) -> int:
    return int(max(0, min(100, round(v))))


# ── main entry ───────────────────────────────────────────────────────────────
def analyze(text: str, title: Optional[str], content_type: str) -> RuleReport:
    low = text.lower()
    sents = _sentences(text)
    paras = _paragraphs(text)
    words = _WORD.findall(text)
    wc = len(words)

    issues: List[RuleIssue] = []
    caps: List[CapHit] = []
    checks: List[CheckItem] = []

    # ── sourcing signals ──────────────────────────────────────────────────
    attributions = sum(low.count(m) for m in C.ATTRIBUTION_MARKERS)
    tiers_present = sorted(
        t for t, terms in C.SOURCE_TIERS.items() if any(x in low for x in terms)
    )
    best_tier = tiers_present[0] if tiers_present else 99

    # ── Research Accuracy (rule part) ─────────────────────────────────────
    acc = 85.0
    unsourced_stats: List[str] = []
    for s in sents:
        sl = s.lower()
        if _STAT.search(s) and not _has_attribution(sl):
            unsourced_stats.append(s.strip())
    for s in unsourced_stats[:6]:
        acc -= 8
        issues.append(RuleIssue(
            "accuracy", "Statistic without a source",
            "Every numerical claim must carry attribution (Constitution §D).",
            "Unsourced figures read as invented and damage credibility.",
            "Attribute the figure to a named source, e.g. “according to [source]”.",
            "high", s[:180],
        ))
    if unsourced_stats:
        top = unsourced_stats[0][:180]
        caps.append(CapHit("unsupported_claim", C.HARD_CAPS["unsupported_claim"].ceiling,
                           C.HARD_CAPS["unsupported_claim"].label, top))

    # sensitive allegations without sourcing
    for s in sents:
        sl = s.lower()
        sensitive = any(t in sl for t in C.HIGH_SCRUTINY_TERMS)
        allegationy = any(w in sl for w in ("alleged", "allegation", "accused", "reportedly", "claim"))
        if sensitive and allegationy and not _has_attribution(sl) and best_tier > 3:
            acc -= 15
            caps.append(CapHit(
                "sensitive_allegation_unsourced",
                C.HARD_CAPS["sensitive_allegation_unsourced"].ceiling,
                C.HARD_CAPS["sensitive_allegation_unsourced"].label, s[:200],
            ))
            issues.append(RuleIssue(
                "accuracy", "Sensitive allegation is unsupported",
                "Sensitive allegations need a primary official source, two independent "
                "credible sources, or documentary evidence (Constitution §C).",
                "Unsupported allegations are a serious reputational and legal risk.",
                "Attribute to a credible source or hedge until it can be verified.",
                "critical", s[:200],
            ))
            break

    # opinion-as-fact
    for marker in C.OPINION_AS_FACT_MARKERS:
        if marker in low:
            idx = low.find(marker)
            sent = _sentence_at(text, idx)
            if not _has_attribution(sent.lower()):
                caps.append(CapHit("opinion_as_fact", C.HARD_CAPS["opinion_as_fact"].ceiling,
                                   C.HARD_CAPS["opinion_as_fact"].label, sent[:180]))
                issues.append(RuleIssue(
                    "accuracy", "Opinion stated as fact",
                    "Absolute value judgements need evidence or should be framed as opinion.",
                    "Blurring opinion and fact undermines a research-first stance.",
                    "Attribute the judgement or reframe it as a clearly-marked view.",
                    "high", sent[:180],
                ))
                break
    checks.append(CheckItem("No unsourced statistics", not unsourced_stats,
                            f"{len(unsourced_stats)} found" if unsourced_stats else ""))

    # ── Credibility & Sourcing ────────────────────────────────────────────
    density = attributions / max(1.0, len(sents) / 3.0)
    if attributions == 0:
        src = 25.0
    else:
        src = 40.0 + min(45.0, density * 45.0)
    tier_bonus = {1: 15, 2: 12, 3: 8, 4: 4}.get(best_tier, 0)
    src += tier_bonus
    if attributions == 0 and wc > 150:
        issues.append(RuleIssue(
            "sourcing", "No attribution anywhere",
            "Important claims require attribution (Constitution §D).",
            "Without sources the piece cannot be trusted as research.",
            "Add credible Tier 1–3 sources for the central claims.",
            "high", None,
        ))
    checks.append(CheckItem("At least one credible (Tier 1–3) source", best_tier <= 3,
                            f"best tier: {best_tier if best_tier < 99 else 'none'}"))
    checks.append(CheckItem("Claims are attributed", attributions > 0,
                            f"{attributions} attributions"))

    # ── Writing Quality ───────────────────────────────────────────────────
    wq = 100.0
    # AI clichés
    cliche_hits = [(p, low.count(p)) for p in C.AI_CLICHES if p in low]
    ct = sum(n for _, n in cliche_hits)
    wq -= min(40, ct * 10)
    for p, _ in cliche_hits[:4]:
        issues.append(RuleIssue(
            "writing", "AI cliché", f"“{p}” is a generic AI phrase the Constitution bans.",
            "Clichés make the writing read as machine-generated.",
            f"Delete or rewrite “{p}” in specific, concrete language.",
            "low", p,
        ))
    # em dash
    em = text.count("—")
    wq -= min(24, em * 6)
    if em:
        issues.append(RuleIssue(
            "writing", "Em dash used", "House style forbids the em dash (Constitution §G).",
            "Breaks the TIES house style.",
            "Replace the em dash with a comma, full stop, or brackets.", "low", None,
        ))
    # bias phrases (neutrality → folded into accuracy + writing)
    bias_hits = [p for p in C.BIAS_PHRASES if re.search(rf"\b{re.escape(p)}\b", low)]
    wq -= min(20, len(bias_hits) * 5)
    acc -= min(15, len(bias_hits) * 5)
    for p in bias_hits[:4]:
        sent = _sentence_at(text, low.find(p))
        issues.append(RuleIssue(
            "accuracy", "Unsupported absolutist phrasing",
            f"“{p}” asserts certainty without evidence (Constitution §E).",
            "Absolutist language signals bias and weakens neutrality.",
            f"Remove “{p}” or back it with evidence.", "medium", sent[:160],
        ))
    # British spelling
    amer = [(a, b) for a, b in C.AMERICAN_SPELLINGS.items()
            if re.search(rf"\b{a}\b", low)]
    wq -= min(15, len(amer) * 3)
    for a, b in amer[:4]:
        issues.append(RuleIssue(
            "writing", "American spelling",
            f"TIES uses British English: “{a}” → “{b}”.",
            "Inconsistent spelling looks unedited.",
            f"Use “{b}”.", "low", a,
        ))
    # excessive bullets
    bullet_lines = len(re.findall(r"(?m)^\s*[-*•]\s+", text))
    if bullet_lines >= 6 and bullet_lines > len(paras):
        wq -= 10
        issues.append(RuleIssue(
            "writing", "Over-reliance on bullet lists",
            "TIES prefers flowing paragraphs over fragmented bullet lists.",
            "Excessive bullets read as notes, not a considered piece.",
            "Convert key bullets into connected prose.", "low", None,
        ))
    # robotic sentence rhythm
    slens = [len(_WORD.findall(s)) for s in sents]
    if len(slens) >= 6:
        mean = sum(slens) / len(slens)
        var = sum((x - mean) ** 2 for x in slens) / len(slens)
        if var < 12:  # very uniform lengths
            wq -= 8
    checks.append(CheckItem("No AI clichés", ct == 0, f"{ct} found" if ct else ""))
    checks.append(CheckItem("No em dash", em == 0, f"{em} found" if em else ""))
    checks.append(CheckItem("British spelling", not amer, f"{len(amer)} US spellings" if amer else ""))
    checks.append(CheckItem("Neutral (no unsupported absolutes)", not bias_hits,
                            ", ".join(bias_hits[:3])))

    # ── Headline ──────────────────────────────────────────────────────────
    if not title or not title.strip():
        hl = 75.0
        checks.append(CheckItem("Headline present", False, "no title supplied"))
    else:
        hl = 90.0
        tl = title.lower()
        clickbait = [m for m in C.CLICKBAIT_MARKERS if m in tl]
        hl -= min(40, len(clickbait) * 20)
        if clickbait:
            issues.append(RuleIssue(
                "headline", "Clickbait headline",
                "The headline uses clickbait phrasing (Constitution §F).",
                "Clickbait erodes a research-first reputation.",
                "Rewrite as a precise, non-sensational headline.", "medium", title,
            ))
        # alignment: content-word overlap with the body
        tw = {w for w in _WORD.findall(tl) if len(w) > 3}
        bw = {w.lower() for w in words if len(w) > 3}
        overlap = (len(tw & bw) / len(tw)) if tw else 1.0
        if tw and overlap < 0.34:
            hl -= 30
            caps.append(CapHit("headline_unsupported", C.HARD_CAPS["headline_unsupported"].ceiling,
                               C.HARD_CAPS["headline_unsupported"].label, title))
            issues.append(RuleIssue(
                "headline", "Headline not supported by the article",
                "The headline’s key terms barely appear in the body (Constitution §C).",
                "A mismatched headline misleads readers.",
                "Align the headline with what the article actually establishes.",
                "high", title,
            ))
        if "!!!" in title or "?!" in title:
            hl -= 10
        checks.append(CheckItem("No clickbait", not clickbait, ", ".join(clickbait[:2])))
        checks.append(CheckItem("Headline matches body", not (tw and overlap < 0.34),
                                f"overlap {overlap:.0%}"))

    # ── Narrative Structure (rule part) ───────────────────────────────────
    nar = 70.0
    if len(paras) >= 4:
        nar += 10
    one_liners = sum(1 for p in paras if len(_WORD.findall(p)) < 14)
    if paras and one_liners / len(paras) > 0.6:
        nar -= 12
    if wc < 120:
        nar -= 15
    nar = _clip(nar)

    # ── Depth (rule part) ─────────────────────────────────────────────────
    dep = 55.0
    if wc > 800:
        dep += 10
    if wc > 1500:
        dep += 10
    mech = ["because", "therefore", "however", "incentive", "system", "mechanism",
            "history", "economics", "psychology", "structural", "underlying",
            "consequence", "trade-off", "trade off", "cause", "effect", "why"]
    mech_hits = sum(low.count(m) for m in mech)
    dep += min(25, mech_hits * 2)
    dep = _clip(dep)

    # ── Original Insight (rule part — weak; AI dominates) ─────────────────
    ins = 60.0
    reveal = ["reveals", "hidden", "counterintuitive", "surprisingly", "what this shows",
              "the real reason", "few realise", "few realize", "turns out"]
    if any(r in low for r in reveal):
        ins += 8
    ins = _clip(ins)

    dim_scores = {
        "accuracy": _clip(acc),
        "insight": ins,
        "narrative": nar,
        "depth": dep,
        "sourcing": _clip(src),
        "writing": _clip(wq),
        "headline": _clip(hl),
    }

    signals = {
        "word_count": wc, "sentences": len(sents), "paragraphs": len(paras),
        "attributions": attributions, "best_tier": best_tier if best_tier < 99 else 0,
        "unsourced_stats": len(unsourced_stats), "cliches": ct, "em_dash": em,
        "bias_phrases": len(bias_hits),
    }
    return RuleReport(dim_scores=dim_scores, caps=caps, issues=issues,
                      checklist=checks, signals=signals)


def _sentence_at(text: str, idx: int) -> str:
    if idx < 0:
        return ""
    start = max(text.rfind(".", 0, idx), text.rfind("\n", 0, idx)) + 1
    end = min(
        [p for p in (text.find(".", idx), text.find("\n", idx)) if p != -1] + [len(text)]
    )
    return text[start:end].strip()
