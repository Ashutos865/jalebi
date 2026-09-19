"""Shared sentence splitter.

This module exists because the same naive pattern was independently written four
times, each carrying the same defects. These tests pin the behaviour so a fifth
copy is never needed — and would fail loudly if one appeared.
"""
from __future__ import annotations

import pytest

from app.text import sentences


# --- the three defects that motivated the module ----------------------------

def test_decimals_stay_intact():
    """'12.7%' split into '12.' and '7%'; the orphan then read as an unsourced
    statistic and tripped the unsupported_claim hard cap."""
    out = sentences.split("Exports rose 12.7% in FY24. Electronics led.")
    assert out == ["Exports rose 12.7% in FY24.", "Electronics led."]


def test_urls_stay_intact():
    """A split URL stops being recognised as a citation."""
    out = sentences.split("Per data (https://commerce.gov.in/report), it rose.")
    assert len(out) == 1
    assert "commerce.gov.in/report" in out[0]


def test_titles_stay_with_their_claim():
    """'Dr. Rao said X' split the attribution off the claim, so an attributed
    statement was analysed as unattributed."""
    out = sentences.split("Dr. Rao said exports rose. The trend held.")
    assert out[0] == "Dr. Rao said exports rose."
    assert len(out) == 2


@pytest.mark.parametrize("abbrev", [
    "Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "St.", "Jr.", "Sr.",
    "Inc.", "Ltd.", "Co.", "etc.", "approx.",
])
def test_common_abbreviations_do_not_end_sentences(abbrev):
    out = sentences.split(f"The report from {abbrev} Smith was clear. It held.")
    assert len(out) == 2, out


# --- ordinary behaviour ------------------------------------------------------

def test_splits_on_terminal_punctuation():
    assert len(sentences.split("One. Two! Three?")) == 3


def test_splits_on_line_breaks():
    assert len(sentences.split("Headline here\nBody text follows")) == 2


def test_handles_quotes_opening_a_sentence():
    out = sentences.split('He paused. "The trend is fragile," she said.')
    assert len(out) == 2
    assert out[1].startswith('"The trend')


def test_trims_and_drops_empties():
    assert sentences.split("  One.   \n\n  Two.  ") == ["One.", "Two."]


@pytest.mark.parametrize("value", ["", None, "   ", "\n\n"])
def test_empty_input_is_safe(value):
    assert sentences.split(value) == []


def test_count_matches_split():
    text = "One. Two. Three."
    assert sentences.count(text) == len(sentences.split(text)) == 3


def test_unicode_is_handled():
    out = sentences.split("भारत का निर्यात बढ़ा। The trend held.")
    assert out, "must not crash or return empty on non-Latin script"


# --- every consumer uses this module ----------------------------------------

def test_all_callers_share_one_implementation():
    """A local regex in a calling module is how this bug came back twice."""
    from app.analysis import analyzers, factcheck
    from app.pipeline import text_features
    from app.scoring import rules

    probe = "Dr. Rao said exports rose 12.7% in FY24. The trend held."
    expected = sentences.split(probe)

    assert analyzers._sentences(probe) == expected
    assert factcheck._sentences(probe) == expected
    assert rules._sentences(probe) == expected
    # text_features uses the same splitter for its sentence statistics.
    assert text_features.sentence_split(probe) == expected


def test_integrity_analysis_keeps_attribution():
    """End-to-end: the bug this refactor fixes."""
    from app.analysis.analyzers import analyze_integrity

    report = analyze_integrity("Dr. Rao said exports rose 12.7% in FY24.")
    assert any("Dr. Rao" in c for c in report.claims), report.claims
