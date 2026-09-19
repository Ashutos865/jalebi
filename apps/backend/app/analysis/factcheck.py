"""Fact-check worklist — SOP §4 "Compulsory Fact-Checking".

The SOP requires the editor to verify *every* claim, statistic and statement of
fact, and to manually click each hyperlinked citation to confirm the source
actually supports it. That is human work; Jalebi's job is to make sure nothing
is missed and to put the riskiest items first.

So this produces a *worklist*, not a verdict. Each item is one claim with the
citation sitting nearest it, ranked by how much verification it needs. Jalebi
does not fetch URLs or judge whether a source supports a claim — it cannot, and
pretending otherwise would be worse than saying nothing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.scoring import constitution as C
from app.text import sentences

_URL = re.compile(r"https?://\S+")
_NUMBER = re.compile(
    # "12.7%" / "12 per cent" / "45 crore" / "3 billion". The unit alternatives
    # are grouped so the trailing \b applies to the words only: a \b after "%"
    # would never match, which silently dropped every percentage.
    r"\d+(?:[.,]\d+)?\s?(?:%|(?:percent|per cent|crore|lakh|billion|million|"
    r"trillion|bn|mn)\b)"
    r"|(?:₹|\$|€|£)\s?\d+(?:[.,]\d+)?",
    re.IGNORECASE,
)
# Calendar years and the Indian fiscal-year forms TIES copy uses (FY24, FY2024,
# FY23-24, 2023-24).
_YEAR = re.compile(
    r"\b(?:19|20)\d{2}\b|\bFY\s?\d{2,4}(?:[-/]\d{2,4})?\b", re.IGNORECASE
)
_QUOTE = re.compile(r"[\"“][^\"”]{12,}[\"”]")

# Claims about these need a primary source, per the SOP's high-scrutiny posture.
_NAMED_ENTITY = re.compile(
    r"\b(?:[A-Z][a-z]{2,}\s+){0,2}"
    r"(?:Ministry|Government|Court|Commission|Authority|Bank|Board|Council|"
    r"Parliament|Department|Agency|Bureau|Institute)\b"
)

RISK_HIGH = "high"
RISK_MEDIUM = "medium"
RISK_LOW = "low"


@dataclass
class FactCheckItem:
    """One claim for the editor to verify."""

    claim: str
    risk: str                       # high | medium | low
    reason: str                     # why it needs checking
    citation: Optional[str] = None  # nearest URL, if any
    source_tier: Optional[int] = None
    has_number: bool = False
    has_quote: bool = False
    verified: bool = False          # the editor ticks this off


@dataclass
class FactCheckList:
    items: List[FactCheckItem] = field(default_factory=list)
    total_claims: int = 0
    uncited_claims: int = 0

    @property
    def high_risk(self) -> List[FactCheckItem]:
        return [i for i in self.items if i.risk == RISK_HIGH]


def _sentences(text: str) -> List[str]:
    return sentences.split(text)


def _nearest_citation(sentence: str, following: str) -> Optional[str]:
    """A URL inside the sentence, or in a footnote line straight after it.

    The following sentence only counts when it is a *reference*, not another
    claim of its own — otherwise a claim silently borrows the next sentence's
    source and looks cited when it is not.
    """
    here = _URL.search(sentence)
    if here:
        return here.group(0)

    nxt = _URL.search(following[:200])
    if not nxt:
        return None
    # A footnote is mostly just the link (plus "See", "Source:" and the like),
    # and asserts nothing itself.
    stripped = _URL.sub("", following).strip(" \t.,;:()[]")
    if len(stripped.split()) <= 4 or re.match(
        r"^(see|source|sources|ref|reference|via|per)\b", stripped, re.IGNORECASE
    ):
        return nxt.group(0)
    return None


def _is_factual_claim(sentence: str) -> bool:
    """Does this sentence assert something checkable?

    Deliberately broad: under-listing a claim means an editor never sees it,
    which is the failure mode the SOP exists to prevent.
    """
    if len(sentence.split()) < 5:
        return False
    if _NUMBER.search(sentence) or _YEAR.search(sentence):
        return True
    if _QUOTE.search(sentence):
        return True
    if _NAMED_ENTITY.search(sentence):
        return True
    low = sentence.lower()
    return any(m in low for m in C.ATTRIBUTION_MARKERS)


def build(text: str) -> FactCheckList:
    """Build the editor's fact-check worklist for `text`."""
    out = FactCheckList()
    sents = _sentences(text)

    for idx, sentence in enumerate(sents):
        if not _is_factual_claim(sentence):
            continue

        out.total_claims += 1
        following = " ".join(sents[idx + 1: idx + 2])
        citation = _nearest_citation(sentence, following)
        has_number = bool(_NUMBER.search(sentence))
        has_quote = bool(_QUOTE.search(sentence))
        tier = C.best_tier(sentence)
        tier = tier if tier != 99 else None

        if citation is None:
            out.uncited_claims += 1

        # Ranking: what would hurt most if it were wrong and nobody looked.
        if has_quote and citation is None:
            risk, reason = RISK_HIGH, "Direct quotation with no linked source — verify wording and attribution."
        elif has_number and citation is None:
            risk, reason = RISK_HIGH, "Statistic with no linked source — the SOP requires every figure be attributable."
        elif has_number and tier is not None and tier >= 5:
            risk, reason = RISK_HIGH, "Statistic resting on a low-tier source — find a primary one."
        elif citation is None and tier is None:
            risk, reason = RISK_MEDIUM, "Factual claim with no citation or named source."
        elif has_number:
            risk, reason = RISK_MEDIUM, "Statistic — open the link and confirm the figure matches."
        elif has_quote:
            risk, reason = RISK_MEDIUM, "Quotation — confirm the wording against the source."
        else:
            risk, reason = RISK_LOW, "Claim is attributed — spot-check the source supports it."

        out.items.append(FactCheckItem(
            claim=sentence, risk=risk, reason=reason, citation=citation,
            source_tier=tier, has_number=has_number, has_quote=has_quote,
        ))

    order = {RISK_HIGH: 0, RISK_MEDIUM: 1, RISK_LOW: 2}
    out.items.sort(key=lambda i: order[i.risk])
    return out
