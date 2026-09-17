"""Source-tier matching against the sources the TIES Content SOP names.

Two defects this pins:
  * Outlets the SOP explicitly approves (Indian Express, Firstpost) and its
    primary research route (Google Scholar) were absent from SOURCE_TIERS, so
    citing them earned a writer no credit.
  * Tiers were matched by plain substring, so "went to university" and "the
    hospital" (containing "pti") scored as credible media sources.
"""
from __future__ import annotations

import pytest

from app.scoring import constitution as C


# --- sources named in the SOP ------------------------------------------------

@pytest.mark.parametrize("outlet", ["Indian Express", "Firstpost", "The Hindu"])
def test_sop_named_media_houses_are_tier_3_or_better(outlet):
    assert C.best_tier(f"{outlet} reported that exports rose 12% in FY24.") <= 3


def test_sop_named_outlets_rank_equally():
    """Citing Firstpost must not be worth less than citing The Hindu."""
    hindu = C.best_tier("The Hindu reported exports rose 12%.")
    express = C.best_tier("The Indian Express reported exports rose 12%.")
    firstpost = C.best_tier("Firstpost reported exports rose 12%.")
    assert hindu == express == firstpost


@pytest.mark.parametrize(
    "phrase",
    ["Google Scholar", "scholar.google.com", "a peer-reviewed study", "doi.org/10.1", "arXiv"],
)
def test_academic_routes_are_tier_1(phrase):
    """The SOP sends authors to Google Scholar for peer-reviewed research."""
    assert C.best_tier(f"Per {phrase}, exports rose 12% in FY24.") == 1


def test_indian_institutions_are_tier_1():
    for inst in ["RBI", "NITI Aayog", "SEBI"]:
        assert C.best_tier(f"{inst} data shows exports rose.") == 1, inst


# --- word-boundary matching --------------------------------------------------

def test_hospital_is_not_press_trust_of_india():
    """'hospital' contains 'pti' — substring matching scored it Tier 2."""
    assert C.best_tier("He was taken to the hospital after the incident.") != 2


def test_partial_words_do_not_match():
    for text in [
        "The captive market grew.",          # contains 'pti'
        "A scriptural reference.",           # contains 'pti'
        "They had no options left.",         # contains 'pti'
    ]:
        assert C.best_tier(text) == 99, text


def test_literal_terms_still_match():
    """Terms that are not plain words must keep working."""
    assert C.best_tier("as reported by (AP) yesterday") == 2
    assert C.best_tier("see scholar.google.com for the paper") == 1


def test_real_citations_still_detected():
    assert C.best_tier("Reuters reported the figure.") == 2
    assert C.best_tier("Ministry of Commerce data shows growth.") == 1
    assert C.best_tier("A post on Twitter claimed otherwise.") == 6


def test_no_source_returns_sentinel():
    assert C.best_tier("Exports rose a lot last year, everyone agrees.") == 99


def test_best_tier_prefers_the_strongest_source():
    text = "A blog post cited Ministry of Commerce data."   # tier 5 and tier 1
    assert C.best_tier(text) == 1
    assert C.tiers_present(text) == [1, 5]


def test_matching_is_case_insensitive():
    assert C.best_tier("REUTERS reported it.") == 2
    assert C.best_tier("firstpost reported it.") == 3
