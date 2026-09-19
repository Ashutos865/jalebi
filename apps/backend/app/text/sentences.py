"""Sentence segmentation — one implementation, used everywhere.

This exists because the naive pattern `[^.!?]+` (and its cousin `(?<=[.!?])\\s+`)
was independently reimplemented four times across the codebase, and each copy
carried the same defects:

  * `12.7%` split into `12.` and `7%`. The orphaned `7%` then read as an
    unsourced statistic and tripped the `unsupported_claim` hard cap, which
    capped a fully-sourced article at 50 — below unsourced hype.
  * `commerce.gov.in` split mid-URL, so a citation stopped being recognised.
  * `Dr. Rao said X` split into `Dr.` and `Rao said X`, severing the attribution
    from the claim so an attributed statement analysed as unattributed.

Every module that needs sentences imports `split()` from here. Adding a new
regex in a calling module is how the bug came back twice; don't.
"""
from __future__ import annotations

import re
from typing import List

# Titles and abbreviations whose trailing period does not end a sentence. Each
# lookbehind sits *after* the (?<=[.!?]) so it inspects the text before the dot.
_ABBREV = (
    r"(?<!\bDr\.)(?<!\bMr\.)(?<!\bMrs\.)(?<!\bMs\.)(?<!\bProf\.)(?<!\bSt\.)"
    r"(?<!\bJr\.)(?<!\bSr\.)(?<!\bvs\.)(?<!\bNo\.)(?<!\bFig\.)(?<!\bEd\.)"
    r"(?<!\bInc\.)(?<!\bLtd\.)(?<!\bCo\.)(?<!\bapprox\.)(?<!\betc\.)"
    r"(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bU\.S\.)(?<!\bU\.K\.)"
)

# Split on terminal punctuation followed by whitespace and something that looks
# like a new sentence (optionally opening quote/bracket, then a capital or a
# digit), or on a hard line break. Decimals, URLs and abbreviations survive.
_SENT_SPLIT = re.compile(
    r"(?<=[.!?])" + _ABBREV + r"\s+(?=[\"“‘(\[]?[A-Z0-9])|\n+"
)


def split(text: str) -> List[str]:
    """Split `text` into trimmed, non-empty sentences.

    Safe on None/empty input; never raises.
    """
    if not text:
        return []
    return [s.strip() for s in _SENT_SPLIT.split(text) if s and s.strip()]


def count(text: str) -> int:
    return len(split(text))
