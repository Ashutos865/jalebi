"""Deterministic analysis of reasoning quality — insight, depth, narrative.

Jalebi is meant to be useful with no API key at all. On that path the AI layer
is absent, so whatever these three dimensions can measure deterministically is
all the signal a writer gets.

The rules this replaces were thin to the point of being misleading. `insight`
returned a flat 60.0 and added 8 if the text contained one of nine phrases like
"surprisingly" — so it rewarded *claiming* insight rather than exhibiting it, and
scored an excellent analytical piece identically to vacuous filler.

The approach here is to look for structural evidence of thinking:

  * **Evidence → conclusion.** Does a claim follow from something stated, or is
    it asserted? Measured by connectives that bind a conclusion to a premise.
  * **Causal chains.** One "because" is a reason; a chain of them is an
    explanation of a mechanism.
  * **Specificity.** Named actors, figures and timeframes distinguish analysis
    from generality. "Exports rose" vs "exports rose 12.7% in FY24".
  * **Comparison and contrast.** Insight usually comes from putting two things
    beside each other.
  * **Counter-argument.** Acknowledging the other case is the clearest textual
    signal of original thought rather than advocacy.
  * **Restatement penalty.** Filler that announces significance without
    supplying it ("this is a big deal", "many people are saying").

None of this detects insight the way a reader does. It detects the *shape* of
reasoned writing, which is strongly correlated and, unlike a model, identical
on every run.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List

from app.text import sentences as _sentences

# --- signal vocabularies -----------------------------------------------------

# A conclusion bound to a stated premise.
INFERENCE = [
    "therefore", "which means", "as a result", "consequently", "so that",
    "this suggests", "this implies", "it follows", "in turn", "hence",
    "the effect is", "that explains", "which is why", "this is because",
]

# Causal mechanism, not just sequence.
CAUSAL = [
    "because", "driven by", "caused by", "stems from", "results from",
    "leads to", "gives rise to", "underpins", "accounts for", "owing to",
    "due to", "triggered by", "depends on",
]

# Two things set beside each other.
COMPARATIVE = [
    "compared with", "compared to", "relative to", "whereas", "unlike",
    "by contrast", "in contrast", "more than", "less than", "against the",
    "versus", " vs ", "the difference", "similarly", "equally",
]

# The writer has considered the other case.
COUNTERPOINT = [
    "however", "although", "though", "yet ", "but the", "critics", "sceptics",
    "skeptics", "on the other hand", "that said", "even so", "nonetheless",
    "nevertheless", "caution", "counterargument", "one objection",
]

# Systemic vocabulary — explaining how something works.
MECHANISM = [
    "incentive", "mechanism", "structural", "underlying", "feedback",
    "trade-off", "trade off", "constraint", "dynamic", "equilibrium",
    "bottleneck", "leverage", "second-order", "knock-on", "spillover",
    "dependency", "threshold", "elasticity",
]

# Announcing importance instead of demonstrating it.
FILLER = [
    "a big deal", "really good news", "many people are saying",
    "it is important to note", "it's important to note", "needless to say",
    "at the end of the day", "the fact of the matter", "goes without saying",
    "time will tell", "only time will tell", "remains to be seen",
    "a lot of people", "everyone knows", "in today's world",
    "game changer", "game-changer", "huge impact", "very significant",
]

# Concrete anchors.
_NUMBER = re.compile(
    r"\d+(?:[.,]\d+)?\s?(?:%|percent|per cent|crore|lakh|billion|million|"
    r"trillion|bn|mn)\b|(?:₹|\$|€|£)\s?\d+(?:[.,]\d+)?", re.IGNORECASE
)
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b|\bFY\s?\d{2,4}(?:[-/]\d{2,4})?\b", re.I)
# A capitalised multi-word name, not at the start of a sentence.
_PROPER_NOUN = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})+")
_WORD = re.compile(r"[A-Za-z']+")


@dataclass
class ReasoningSignals:
    """Counts and derived scores. Counts are exposed so the UI can explain a
    score rather than just assert one."""

    inference: int = 0
    causal: int = 0
    comparative: int = 0
    counterpoint: int = 0
    mechanism: int = 0
    filler: int = 0
    specifics: int = 0          # numbers + years + named entities
    word_count: int = 0
    sentence_count: int = 0

    insight: float = 60.0
    depth: float = 55.0
    narrative: float = 70.0

    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, int]:
        return {
            "inference": self.inference, "causal": self.causal,
            "comparative": self.comparative, "counterpoint": self.counterpoint,
            "mechanism": self.mechanism, "filler": self.filler,
            "specifics": self.specifics,
        }


@lru_cache(maxsize=16)
def _vocab_pattern(needles: tuple) -> "re.Pattern[str]":
    """One alternation over a vocabulary, longest phrase first.

    Longest-first matters because these lists overlap: "compared to" must win
    over "compared", and "nonetheless" must not be split. Word boundaries are
    applied only where a term starts or ends with a word character, so entries
    written with deliberate spaces (" vs ", "yet ") keep their meaning.
    """
    parts = []
    for needle in sorted(needles, key=len, reverse=True):
        esc = re.escape(needle)
        if needle[:1].isalnum():
            esc = r"\b" + esc
        if needle[-1:].isalnum():
            esc = esc + r"\b"
        parts.append(esc)
    return re.compile("|".join(parts), re.IGNORECASE)


def _count(haystack: str, needles: List[str]) -> int:
    """How many distinct occurrences of a vocabulary appear in `haystack`.

    Two bugs lived in the one-line `sum(haystack.count(n) ...)` this replaces.
    It counted substrings, so "precaution" scored a counterpoint via "caution"
    -- the seventh instance of that bug class in this codebase. And it let
    several needles claim the same span, so "although" counted twice (as
    "although" and "though") and one concession earned double credit.

    Scanning once with a single alternation fixes both: each position in the
    text is consumed by at most one term.
    """
    return len(_vocab_pattern(tuple(needles)).findall(haystack))


def _per_100_words(count: int, words: int) -> float:
    """Density, so a long piece is not rewarded for mere repetition."""
    return (count / words * 100) if words else 0.0


def analyse(text: str, *, paragraphs: int = 0) -> ReasoningSignals:
    """Measure reasoning structure in `text`. Pure and deterministic."""
    s = ReasoningSignals()
    if not text or not text.strip():
        return s

    low = text.lower()
    words = _WORD.findall(text)
    sents = _sentences.split(text)
    s.word_count = len(words)
    s.sentence_count = len(sents)
    if s.word_count == 0:
        return s

    s.inference = _count(low, INFERENCE)
    s.causal = _count(low, CAUSAL)
    s.comparative = _count(low, COMPARATIVE)
    s.counterpoint = _count(low, COUNTERPOINT)
    s.mechanism = _count(low, MECHANISM)
    s.filler = _count(low, FILLER)
    s.specifics = (
        len(_NUMBER.findall(text))
        + len(_YEAR.findall(text))
        + len(set(_PROPER_NOUN.findall(text)))
    )

    # --- Insight -------------------------------------------------------------
    # Built from evidence of reasoning, capped per signal so no single pattern
    # can be gamed by repetition.
    ins = 50.0
    ins += min(12, _per_100_words(s.inference, s.word_count) * 8)
    ins += min(10, _per_100_words(s.comparative, s.word_count) * 6)
    ins += min(12, _per_100_words(s.counterpoint, s.word_count) * 6)
    ins += min(8, _per_100_words(s.specifics, s.word_count) * 2)
    # Filler actively announces significance instead of showing it.
    ins -= min(20, s.filler * 6)
    s.insight = max(0.0, min(100.0, ins))

    if s.filler:
        s.notes.append(
            f"{s.filler} phrase(s) assert significance without supplying it."
        )
    if s.inference == 0 and s.word_count > 80:
        s.notes.append(
            "No conclusion is drawn from stated evidence — claims are asserted."
        )
    if s.counterpoint == 0 and s.word_count > 150:
        s.notes.append("No counter-argument or caveat is acknowledged.")

    # --- Depth ---------------------------------------------------------------
    # Explaining a mechanism, not accumulating words.
    dep = 50.0
    dep += min(18, _per_100_words(s.causal, s.word_count) * 9)
    dep += min(16, _per_100_words(s.mechanism, s.word_count) * 8)
    dep += min(10, _per_100_words(s.specifics, s.word_count) * 2.5)
    # A causal chain (several linked reasons) beats one stray "because".
    if s.causal >= 3 and s.mechanism >= 2:
        dep += 6
    s.depth = max(0.0, min(100.0, dep))

    if s.causal == 0 and s.word_count > 80:
        s.notes.append("Nothing is explained causally — the piece reports without analysing.")

    # --- Narrative -----------------------------------------------------------
    nar = 62.0
    if paragraphs >= 4:
        nar += 8
    # Varied sentence length reads as considered prose; uniform length is robotic.
    lengths = [len(_WORD.findall(x)) for x in sents] or [0]
    if len(lengths) >= 5:
        mean = sum(lengths) / len(lengths)
        spread = (sum((l - mean) ** 2 for l in lengths) / len(lengths)) ** 0.5
        if mean and spread / mean > 0.35:
            nar += 8
        elif mean and spread / mean < 0.15:
            nar -= 8
            s.notes.append("Sentence lengths are uniform — the rhythm reads as generated.")
    # Transitions carry a reader between ideas.
    nar += min(10, _per_100_words(s.inference + s.counterpoint, s.word_count) * 5)
    if s.word_count < 120:
        nar -= 12
    s.narrative = max(0.0, min(100.0, nar))

    return s
