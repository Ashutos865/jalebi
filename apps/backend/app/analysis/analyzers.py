"""Editorial integrity analyzers (P6).

Heuristic, dependency-free checks that surface research-integrity risks: extracted
factual claims, unattributed/high-risk claims (hallucination surface), citation gaps,
and loaded/biased language. These run standalone (POST /api/integrity) and can feed a
future LLM verification pass. Heuristics are deliberately conservative and explainable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from app.text import sentences

_NUM = re.compile(r"\b\d[\d,.]*\s?(%|percent|billion|million|crore|lakh|bn|mn)?\b", re.I)
_YEAR = re.compile(r"\b(19|20)\d{2}\b")
# Word boundaries, and no bare "(".
#
# Without \b, "pti" matched inside corruption/adoption/consumption/exemption and
# "cited" inside "excited", so a document with no sources at all reported a 36%
# citation density. The bare "(" alternative was worse: adding a parenthetical
# aside to any sentence — "(a strong result)" — made an unattributed claim look
# cited and erased a high-severity finding.
_CITED_NEAR = re.compile(
    r"(?:\baccording to\b|\bper\b|\bas reported\b|\bstud(?:y|ies)\b|"
    r"\bdata from\b|\bsources?\b|\bcited\b|https?://|\bsaid\b|"
    r"\breuters\b|\bpti\b|\bministry\b|\brbi\b|\breports?\b)", re.I,
)
_CLAIM_VERBS = re.compile(
    r"\b(is|are|was|were|will|has|have|rose|fell|grew|increased|decreased|reached|"
    r"found|shows|reveals|proves|causes|leads to)\b", re.I,
)
_HEDGE = re.compile(
    r"\b(some say|many believe|experts believe|it is said|arguably|reportedly|"
    r"allegedly|sources suggest)\b", re.I,
)
BIAS_TERMS = [
    "clearly", "obviously", "undeniably", "everyone knows", "disaster", "catastrophe",
    "regime", "so-called", "radical", "extremist", "shocking", "outrageous", "slammed",
    "blasted", "destroyed", "triumph", "genius", "corrupt", "propaganda", "brilliant",
]
ABSOLUTES = ["always", "never", "everyone", "no one", "all ", "none ", "impossible",
             "guaranteed", "proven fact", "without doubt"]


@dataclass
class Finding:
    type: str          # claim | unattributed_claim | citation_gap | bias | absolute | hedge
    severity: str      # high | medium | low
    text: str
    note: str


@dataclass
class IntegrityReport:
    claims: List[str] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    citation_density: float = 0.0     # cited signals per 100 words
    integrity_score: int = 100        # 0-100, higher = fewer integrity risks


def _sentences(text: str) -> List[str]:
    # Shared splitter: the local regex here severed "Dr. Rao said X" into "Dr."
    # and "Rao said X", so an attributed claim was analysed as unattributed.
    return sentences.split(text)


def _looks_like_claim(s: str) -> bool:
    has_evidence_shape = bool(_NUM.search(s) or _YEAR.search(s))
    return bool(_CLAIM_VERBS.search(s)) and (has_evidence_shape or len(s.split()) > 6)


def analyze_integrity(text: str) -> IntegrityReport:
    report = IntegrityReport()
    sentences = _sentences(text)
    words = max(1, len(re.findall(r"\b\w+\b", text)))
    cited_signals = len(_CITED_NEAR.findall(text))
    report.citation_density = round(cited_signals / words * 100, 2)

    penalty = 0
    for s in sentences:
        low = s.lower()
        is_claim = _looks_like_claim(s)
        cited = bool(_CITED_NEAR.search(s))
        has_number = bool(_NUM.search(s))

        if is_claim:
            report.claims.append(s)

        # Unattributed quantitative claim → hallucination/accuracy surface.
        if is_claim and has_number and not cited:
            report.findings.append(Finding(
                "unattributed_claim", "high", s,
                "Quantitative claim with no nearby source — verify and attribute.",
            ))
            penalty += 6
        elif is_claim and not cited:
            report.findings.append(Finding(
                "citation_gap", "medium", s,
                "Factual claim without attribution.",
            ))
            penalty += 2

        for term in BIAS_TERMS:
            if term in low:
                report.findings.append(Finding(
                    "bias", "medium", s, f"Loaded/charged wording: '{term}'.",
                ))
                penalty += 3
                break
        for term in ABSOLUTES:
            if term in low:
                report.findings.append(Finding(
                    "absolute", "low", s, f"Absolute claim: '{term.strip()}'.",
                ))
                penalty += 1
                break
        if _HEDGE.search(s):
            report.findings.append(Finding(
                "hedge", "low", s, "Vague attribution — name the source.",
            ))
            penalty += 1

    report.integrity_score = max(0, 100 - penalty)
    return report
