"""Nation-First review queue — SOP §4 "Zero Tolerance for Anti-National Narratives".

The SOP asks editors to catch "biased claims, unverified rhetoric, or
manipulated facts that go against the country or undermine the national image".
It asks for that in the same document that demands evidence-based reporting and
peer-reviewed sourcing.

Those two demands only conflict if you filter on *topic*. They agree if you
filter on *evidence*. So this module never judges whether a claim is pro- or
anti-national — it has no way to know, and a tool that guessed would suppress
exactly the well-sourced accountability journalism the SOP also requires.

What it flags is narrower and defensible: a **strongly negative or absolute
claim about a national institution that carries no source**. A sourced version
of the identical sentence is not flagged. That is "unverified rhetoric" as the
SOP defines it, and it leaves the editorial judgement where the SOP puts it —
with the editor.

Output is a review queue. It never changes the score.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from app.analysis.factcheck import _sentences
from app.scoring import constitution as C

_URL = re.compile(r"https?://\S+")

# Subjects the mandate is about: the country and its institutions.
NATIONAL_SUBJECTS = re.compile(
    r"\b(?:India|Indian|Bharat|New Delhi|the nation|the country|"
    r"(?:the\s+)?(?:Union\s+)?Government(?:\s+of\s+India)?|"
    r"Parliament|Lok Sabha|Rajya Sabha|Supreme Court|High Court|"
    r"the [Aa]rmy|the [Nn]avy|the [Aa]ir [Ff]orce|armed forces|military|"
    r"RBI|Reserve Bank of India|NITI Aayog|ISRO|DRDO|"
    r"Prime Minister|President of India|Election Commission)\b"
)

# Language that asserts damage or failure rather than reporting it.
DISPARAGEMENT = re.compile(
    r"\b(?:failed|failure|collapsed?|collapse|disaster|disastrous|catastrophic|"
    r"corrupt|corruption|rigged|fraudulent|sham|puppet|apartheid|fascist|"
    r"authoritarian|rogue|pariah|illegitimate|oppressive|tyranny|tyrannical|"
    r"crumbling|shameful|disgrace|humiliation|humiliated|backward|"
    r"worst|pathetic|useless|hopeless)\b",
    re.IGNORECASE,
)

# Absolutes that turn an argument into a verdict.
ABSOLUTE = re.compile(
    r"\b(?:always|never|every single|no one|nobody|entirely|completely|totally|"
    r"utterly|wholly|absolutely|without exception|all of them)\b",
    re.IGNORECASE,
)

# Negative framing that, combined with an absolute, reads as a verdict against
# the subject rather than a report about it.
NEGATIVE_CONTEXT = re.compile(
    r"\b(?:lag(?:s|ged|ging)?|behind|worse|declin\w+|fall\w*|fell|weak\w*|"
    r"poor(?:ly|est)?|struggl\w+|deteriorat\w+|neglect\w*|deni\w+|"
    r"suppress\w+|violat\w+|abus\w+|unable|incapable|refus\w+)\b",
    re.IGNORECASE,
)

SEVERITY_REVIEW = "review"    # editor should look
SEVERITY_NOTE = "note"        # worth a glance


@dataclass
class NationFirstFlag:
    sentence: str
    severity: str
    reason: str
    subject: str                      # what national subject was matched
    has_source: bool = False


@dataclass
class NationFirstReview:
    flags: List[NationFirstFlag] = field(default_factory=list)
    sentences_examined: int = 0

    @property
    def needs_review(self) -> bool:
        return any(f.severity == SEVERITY_REVIEW for f in self.flags)


def _is_sourced(sentence: str) -> bool:
    """Does this sentence carry evidence — a link, an attribution, or a source?

    The national subject is removed before looking for a source tier: otherwise
    "the Government is corrupt" counts as *citing* the government, because
    "government" is itself a tier-1 source keyword. Naming who you are writing
    about is not evidence.
    """
    if _URL.search(sentence):
        return True

    low = sentence.lower()
    if any(marker in low for marker in C.ATTRIBUTION_MARKERS):
        return True

    without_subject = NATIONAL_SUBJECTS.sub(" ", sentence)
    return C.best_tier(without_subject) != 99


def review(text: str) -> NationFirstReview:
    """Build the Nation-First review queue for `text`.

    Only unsourced disparagement or absolutes about a national subject are
    raised. Sourced criticism is deliberately left alone: under the SOP it is
    legitimate reporting, not a breach.
    """
    out = NationFirstReview()

    for sentence in _sentences(text):
        out.sentences_examined += 1
        subject = NATIONAL_SUBJECTS.search(sentence)
        if not subject:
            continue

        disparaging = DISPARAGEMENT.search(sentence)
        absolute = ABSOLUTE.search(sentence)
        # An absolute only matters here when it is also negative. The mandate is
        # about claims that *undermine* the national image; "India has always led
        # the world" is unsourced praise, which is a sourcing question for the
        # rules engine, not a Nation-First concern.
        if absolute and not disparaging and not NEGATIVE_CONTEXT.search(sentence):
            continue
        if not (disparaging or absolute):
            continue

        sourced = _is_sourced(sentence)
        if sourced:
            # Evidence-based criticism is what the SOP asks for. Not flagged.
            continue

        if disparaging:
            reason = (
                f"Strongly negative claim about {subject.group(0)} with no source "
                f"or attribution — the SOP treats unverified rhetoric about the "
                f"nation as a breach. Attribute it or soften it."
            )
            severity = SEVERITY_REVIEW
        else:
            reason = (
                f"Absolute claim about {subject.group(0)} with no source. "
                f"Absolutes rarely survive scrutiny; qualify or cite it."
            )
            severity = SEVERITY_NOTE

        out.flags.append(NationFirstFlag(
            sentence=sentence, severity=severity, reason=reason,
            subject=subject.group(0), has_source=sourced,
        ))

    order = {SEVERITY_REVIEW: 0, SEVERITY_NOTE: 1}
    out.flags.sort(key=lambda f: order[f.severity])
    return out
