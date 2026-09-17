"""TIES Content SOP — mechanical compliance checks.

These are the parts of the SOP a machine can settle without judgment: is the
header block filled in, is the piece inside its word window, does it use
subheadings, is there a references section with real links.

Deliberately reported as a **separate checklist**, not folded into the editorial
score. The SOP's process rules and the Constitution's quality rubric answer
different questions ("did the writer follow the procedure?" vs "is the writing
any good?"), and collapsing them would make a well-written piece look bad for a
missing Instagram handle.

Not covered here, on purpose:
  * Font / spacing / alignment — discarded by the plain-text export; would need
    the Google Docs API.
  * AI % and plagiarism % — must come from a real detector, not a guess; these
    are recorded from the editor's tooling, never estimated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.scoring import constitution as C
from app.scoring.sop_header import SopHeader, writing_for_is_valid

# Markdown-ish heading, or a short standalone line that reads like a subheading.
_MD_HEADING = re.compile(r"^[ \t]*#{2,3}[ \t]+\S", re.MULTILINE)
_BULLET = re.compile(r"(?m)^[ \t]*(?:[-*•]|\d+[.)])[ \t]+\S")
_URL = re.compile(r"https?://\S+")

# A short line with no terminal punctuation, surrounded by blank lines, is how a
# subheading survives a plain-text export.
_BARE_HEADING = re.compile(
    r"(?m)^(?![ \t]*[-*•])[ \t]*(?P<h>[A-Z][^\n.!?:]{3,70})[ \t]*$"
)

SEVERITY_REQUIRED = "required"   # SOP says must
SEVERITY_ADVISORY = "advisory"   # SOP says should, or we cannot fully verify


@dataclass
class SopCheck:
    name: str
    passed: bool
    detail: str = ""
    severity: str = SEVERITY_REQUIRED

    @property
    def blocking(self) -> bool:
        return self.severity == SEVERITY_REQUIRED and not self.passed


@dataclass
class SopReport:
    checks: List[SopCheck] = field(default_factory=list)
    word_count: int = 0
    word_min: Optional[int] = None
    word_max: Optional[int] = None

    @property
    def failures(self) -> List[SopCheck]:
        return [c for c in self.checks if not c.passed]

    @property
    def blocking_failures(self) -> List[SopCheck]:
        return [c for c in self.checks if c.blocking]

    @property
    def compliant(self) -> bool:
        return not self.blocking_failures

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)


def count_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9'’-]+", text))


def has_subheadings(body: str) -> bool:
    """True if the article is broken up rather than a flat wall of text."""
    if _MD_HEADING.search(body):
        return True
    # Bare-line subheadings: require more than one so a stray capitalised line
    # (or a one-paragraph piece) does not count.
    return len(_BARE_HEADING.findall(body)) >= 2


def has_lists(body: str) -> bool:
    return bool(_BULLET.search(body))


def word_window_for(content_type: str, word_min: Optional[int], word_max: Optional[int]):
    """Resolve the word window: explicit assignment values win, else the SOP
    default for short-form. Long-form has no fixed window in the SOP."""
    if word_min is not None or word_max is not None:
        return word_min, word_max
    if C.is_short_form(content_type):
        return C.SHORT_FORM_WORD_MIN, C.SHORT_FORM_WORD_MAX
    return None, None


def evaluate(
    header: SopHeader,
    body: str,
    content_type: str,
    word_min: Optional[int] = None,
    word_max: Optional[int] = None,
) -> SopReport:
    """Run every mechanical SOP check over an already-parsed document."""
    report = SopReport()
    add = report.checks.append

    # --- 1. Header block ------------------------------------------------------
    add(SopCheck(
        "SOP header block present", header.present,
        "" if header.present else "Paste the pre-drafting metadata block at the top.",
    ))

    if header.present:
        add(SopCheck(
            "All author fields filled", not header.missing,
            ", ".join(header.missing) + " missing" if header.missing else "",
        ))
        wf = header.get("writing_for")
        add(SopCheck(
            "WRITING FOR is a valid destination",
            bool(wf) and writing_for_is_valid(wf),
            f"got {wf!r}; expected TIES Website / Substack / LinkedIn / Main Page"
            if wf and not writing_for_is_valid(wf) else "",
        ))
        add(SopCheck(
            "Content-start marker present", header.has_content_marker,
            "" if header.has_content_marker
            else "Add '(YOUR CONTENT STARTS HERE)' below the header.",
            SEVERITY_ADVISORY,
        ))
        if header.missing_editor:
            add(SopCheck(
                "Editor fields filled", False,
                ", ".join(header.missing_editor) + " (editor completes these)",
                SEVERITY_ADVISORY,
            ))

    # --- 2. Word count --------------------------------------------------------
    wc = count_words(body)
    lo, hi = word_window_for(content_type, word_min, word_max)
    report.word_count, report.word_min, report.word_max = wc, lo, hi
    if lo is not None or hi is not None:
        under = lo is not None and wc < lo
        over = hi is not None and wc > hi
        window = f"{lo}–{hi}" if lo is not None and hi is not None else (
            f"at least {lo}" if lo is not None else f"at most {hi}"
        )
        if under:
            detail = f"{wc} words — {window} required; expand by ~{lo - wc}."
        elif over:
            detail = f"{wc} words — {window} required; trim ~{wc - hi}."
        else:
            detail = f"{wc} words"
        add(SopCheck(f"Word count within {window}", not (under or over), detail))

    # --- 3. Structure ---------------------------------------------------------
    add(SopCheck(
        "Subheadings break up the text", has_subheadings(body),
        "" if has_subheadings(body)
        else "Add H2/H3 subheadings — the SOP prohibits flat, unbroken text.",
    ))
    add(SopCheck(
        "Uses lists or key takeaways", has_lists(body),
        "" if has_lists(body)
        else "Add bullets, a numbered list, or key takeaways.",
        SEVERITY_ADVISORY,
    ))

    # --- 4. References --------------------------------------------------------
    add(SopCheck(
        "References section present", header.has_references,
        "" if header.has_references
        else "Add a 'References' (or 'Footnotes / Links') heading listing every source.",
    ))
    if header.has_references:
        n = len(header.reference_urls)
        add(SopCheck(
            "References contain links", n > 0,
            f"{n} link{'s' if n != 1 else ''}" if n else "no URLs found under the heading",
        ))

    return report
