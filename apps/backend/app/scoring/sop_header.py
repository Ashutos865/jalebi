"""TIES Content SOP — pre-drafting header block.

The SOP requires every draft to open with a fixed metadata block, then the marker
`(YOUR CONTENT STARTS HERE)`, then the article, then a references section.

Jalebi extracts the whole Google Doc as plain text, so without this module the
header is graded as if it were prose. Measured effect on a compliant draft:
word count +40 (against a strict 300-350 window), sourcing 100 -> 76, and
headline 60 -> 90 because the `HEADING:` line accidentally satisfied the
headline check. Parsing the header out is therefore a correctness fix, not only
a compliance feature.

This module is deliberately tolerant about *form* and strict about *presence*:
writers paste the block by hand, so it accepts case differences, curly quotes,
missing colons and reordered fields, and reports what is genuinely absent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Field label -> canonical key. Order is the SOP's own order.
HEADER_FIELDS: List[Tuple[str, str]] = [
    ("WRITING FOR", "writing_for"),
    ("HEADING", "heading"),
    ("SUB-HEADING", "sub_heading"),
    ("AUTHOR'S NAME", "author_name"),
    ("AUTHOR'S INSTAGRAM ID", "author_instagram"),
    ("EDITOR'S NAME", "editor_name"),
    ("DATE OF ASSIGNMENT", "date_of_assignment"),
    ("DATE OF SUBMISSION", "date_of_submission"),
    ("DATE OF EDITING", "date_of_editing"),
]

# Fields an author cannot reasonably fill at drafting time: the editor sets them
# later in the loop. Absence is reported but is not an author-side failure.
EDITOR_FILLED = frozenset({"editor_name", "date_of_editing"})

# Allowed values for WRITING FOR (SOP: TIES Website / Substack / LinkedIn / Main Page).
WRITING_FOR_CHOICES = ("ties website", "substack", "linkedin", "main page")

# Apostrophes vary (straight vs curly) once a writer pastes into Google Docs.
_APOS = r"['‘’ʼ]"

# Match "LABEL:" at the start of a line, tolerating case, spacing and bold markers.
_FIELD_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    (
        key,
        re.compile(
            r"^[ \t>*_#-]*"
            + label.replace("'", _APOS).replace(" ", r"[ \t]+").replace("-", r"[-‐-―]")
            + r"[ \t]*:?[ \t]*(?P<value>.*)$",
            re.IGNORECASE | re.MULTILINE,
        ),
    )
    for label, key in HEADER_FIELDS
]

_CONTENT_START = re.compile(
    r"^[ \t>*_#(-]*YOUR[ \t]+CONTENT[ \t]+STARTS[ \t]+HERE[ \t)*_]*$",
    re.IGNORECASE | re.MULTILINE,
)

# The references section: the SOP's own wording, plus the common variants writers
# actually use.
_REFERENCES_HEADING = re.compile(
    r"^[ \t>*_#-]*(?:"
    r"FOOTNOTES?[ \t]*/?[ \t]*LINKS?(?:[ \t]+TO[ \t]+ALL[ \t]+YOUR[ \t]+REFERENCES)?"
    r"|REFERENCES?"
    r"|SOURCES?"
    r"|BIBLIOGRAPHY"
    r"|CITATIONS?"
    r")[ \t]*:?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

_URL = re.compile(r"https?://\S+")

# A placeholder the writer pasted but never filled, e.g. "[TIES Website / Substack …]".
_UNFILLED = re.compile(r"^\[.*\]$")


@dataclass
class SopHeader:
    """Parsed SOP header block and the document split around it."""

    present: bool = False
    fields: Dict[str, str] = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)      # labels, author-fillable
    missing_editor: List[str] = field(default_factory=list)  # labels, editor-filled
    has_content_marker: bool = False
    has_references: bool = False

    body: str = ""            # the article alone — what scoring must grade
    references: str = ""      # the references section, verbatim
    reference_urls: List[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        """All author-fillable fields present, plus both structural markers."""
        return self.present and not self.missing and self.has_content_marker

    def get(self, key: str) -> str:
        return self.fields.get(key, "")


def _clean_value(raw: str) -> str:
    """Strip bold/italic markers and stray punctuation a writer pasted around
    the value, e.g. '**Substack**' or '__Someone__'."""
    v = raw.strip()
    # A bold label ("**Writing For:**") leaves its closing marker on the value.
    v = re.sub(r"^[*_]+", "", v)
    v = re.sub(r"[*_]+$", "", v)
    return v.strip()


def _looks_filled(value: str) -> bool:
    v = value.strip().strip("_").strip()
    if not v or _UNFILLED.match(v):
        return False
    # "N/A" and friends count as answered.
    return True


def parse(text: str) -> SopHeader:
    """Parse the SOP header from `text` and split off body + references.

    Always returns a usable result: when no header is found, `body` is the whole
    input, so callers can grade any document unchanged.
    """
    out = SopHeader()
    if not text:
        return out

    # The header block lives at the top. Bound the search so a "HEADING:" line
    # deep in the article cannot be mistaken for the metadata block.
    marker = _CONTENT_START.search(text)
    search_region = text[: marker.start()] if marker else text[:2000]

    for key, pattern in _FIELD_PATTERNS:
        m = pattern.search(search_region)
        if m:
            value = _clean_value(m.group("value"))
            if _looks_filled(value):
                out.fields[key] = value

    label_for = {key: label for label, key in HEADER_FIELDS}
    found_any = bool(out.fields)
    # A lone "HEADING:" line is not a header block; require real evidence.
    out.present = found_any and (marker is not None or len(out.fields) >= 3)

    if out.present:
        for _label, key in HEADER_FIELDS:
            if key not in out.fields:
                target = out.missing_editor if key in EDITOR_FILLED else out.missing
                target.append(label_for[key])

    # --- split body -----------------------------------------------------------
    if marker:
        out.has_content_marker = True
        body = text[marker.end():]
    elif out.present:
        # Header without the marker: drop up to the last matched field line.
        last_end = 0
        for key, pattern in _FIELD_PATTERNS:
            if key in out.fields:
                m = pattern.search(search_region)
                if m:
                    last_end = max(last_end, m.end())
        body = text[last_end:]
    else:
        body = text

    # --- split references -----------------------------------------------------
    ref_match = _REFERENCES_HEADING.search(body)
    if ref_match:
        out.has_references = True
        out.references = body[ref_match.end():].strip()
        out.reference_urls = _URL.findall(out.references)
        body = body[: ref_match.start()]

    out.body = body.strip()
    return out


def scoring_text(text: str) -> str:
    """The portion of `text` that should be graded as prose.

    Strips the SOP header and the references list, which are metadata rather than
    writing. Falls back to the original text when no header is present, so
    non-SOP documents are unaffected.
    """
    parsed = parse(text)
    return parsed.body or text


def writing_for_is_valid(value: str) -> bool:
    v = value.strip().lower().rstrip(".")
    return any(choice in v for choice in WRITING_FOR_CHOICES)


def missing_label_list(header: SopHeader) -> Optional[str]:
    """Human-readable summary of what the author still has to fill in."""
    if not header.missing:
        return None
    return ", ".join(header.missing)
