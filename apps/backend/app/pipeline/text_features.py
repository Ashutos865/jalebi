"""Text feature extraction.

Pure, dependency-free analysis of a document. The mock reviewer keys its scores and
issues off these features so its feedback is genuinely about the submitted text
(not random). When Claude replaces the mock (P2), these same features can be passed
into the prompt as structured signals.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

# Signals the Editorial DNA cares about.
AI_CLICHES = [
    "delve", "tapestry", "moreover", "furthermore", "in today's fast-paced",
    "it's important to note", "it is important to note", "in conclusion",
    "unlock", "leverage", "navigate the", "landscape", "realm", "testament to",
    "ever-evolving", "ever evolving", "game-changer", "game changer",
    "at the end of the day", "when it comes to", "a myriad of", "seamless",
]
SENSATIONAL = [
    "shocking", "unbelievable", "you won't believe", "insane", "destroyed",
    "slams", "blasts", "epic", "mind-blowing", "jaw-dropping", "bombshell",
    "explosive", "outrageous", "!!!", "must-read", "will change everything",
]
HEDGES = [
    "many people", "some say", "experts believe", "it is said", "arguably",
    "some argue", "a lot of", "lots of", "sort of", "kind of", "basically",
    "literally", "very ", "really ", "clearly ", "obviously ",
]
CITATION_CUES = [
    "according to", "as reported by", "cited", "study found", "research shows",
    "data from", "per ", "sources say", "(", "http://", "https://",
]
CONTEXT_CUES = [
    "history", "historically", "in 19", "in 20", "context", "background",
    "strategic", "economic", "gdp", "policy", "india", "global", "geopolit",
]


@dataclass
class TextFeatures:
    word_count: int = 0
    sentence_count: int = 0
    paragraph_count: int = 0
    avg_sentence_len: float = 0.0
    headline: str = ""
    long_sentences: int = 0            # sentences > 30 words
    number_count: int = 0
    url_count: int = 0
    quote_count: int = 0               # quoted passages ("...")
    citation_signal: int = 0
    context_signal: int = 0
    ai_cliches: List[str] = field(default_factory=list)
    sensational_terms: List[str] = field(default_factory=list)
    hedges: List[str] = field(default_factory=list)
    passive_hits: int = 0
    longest_sentence: str = ""


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"\b[\w'-]+\b")
_PASSIVE = re.compile(r"\b(was|were|is|are|been|be|being)\s+\w+(ed|en)\b", re.I)


def _find_terms(text_lower: str, terms: List[str]) -> List[str]:
    return [t.strip() for t in terms if t in text_lower]


def analyze(text: str) -> TextFeatures:
    text = text.strip()
    lower = text.lower()
    f = TextFeatures()

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    f.headline = lines[0] if lines else ""
    f.paragraph_count = len([b for b in re.split(r"\n\s*\n", text) if b.strip()]) or (
        1 if text else 0
    )

    words = _WORD.findall(text)
    f.word_count = len(words)

    sentences = [s for s in _SENT_SPLIT.split(text) if s.strip()]
    f.sentence_count = len(sentences)
    if sentences:
        lengths = [(s, len(_WORD.findall(s))) for s in sentences]
        f.avg_sentence_len = round(sum(l for _, l in lengths) / len(lengths), 1)
        f.long_sentences = sum(1 for _, l in lengths if l > 30)
        longest = max(lengths, key=lambda x: x[1])
        f.longest_sentence = longest[0].strip() if longest[1] > 30 else ""

    f.number_count = len(re.findall(r"\b\d[\d,.%]*\b", text))
    f.url_count = len(re.findall(r"https?://\S+", text))
    f.quote_count = len(re.findall(r"[\"“][^\"”]{8,}[\"”]", text))
    f.citation_signal = sum(lower.count(c) for c in CITATION_CUES)
    f.context_signal = sum(1 for c in CONTEXT_CUES if c in lower)
    f.ai_cliches = _find_terms(lower, AI_CLICHES)
    f.sensational_terms = _find_terms(lower, SENSATIONAL)
    f.hedges = _find_terms(lower, HEDGES)
    f.passive_hits = len(_PASSIVE.findall(text))
    return f


def snippet(text: str, term: str, width: int = 90) -> str:
    """Return a short quote around the first occurrence of `term`, for issue.quote."""
    idx = text.lower().find(term.lower())
    if idx == -1:
        return ""
    start = max(0, idx - width // 3)
    end = min(len(text), idx + len(term) + width)
    frag = text[start:end].strip().replace("\n", " ")
    return ("…" if start > 0 else "") + frag + ("…" if end < len(text) else "")
