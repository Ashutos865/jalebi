"""Whole-word matching for every keyword list.

This bug class has now appeared five separate times in this codebase:

    "corruption"   contained "pti"   -> counted as a Press Trust of India citation
    "hospital"     contained "pti"   -> counted as a tier-2 source
    "went to university"             -> counted as a tier-3 media source
    "unsaid"       contained "said"  -> counted as an attribution
    "warehouse"    contained "war"   -> tripped the sensitive-allegation hard cap

The last one is the worst: three innocent business sentences were capped at 45
because a warehouse manager "claimed" something.

Every keyword list now goes through C.matches_any / count_matches, which match
on word boundaries while still allowing ordinary inflections. These tests pin
both halves — no false positives, and no lost real matches.
"""
from __future__ import annotations

import pytest

from app.scoring import constitution as C
from app.scoring import rules


# --- the false positives that motivated this -------------------------------

@pytest.mark.parametrize("text,word", [
    ("The warehouse burned down overnight.", "war"),
    ("He took a forward-looking view.", "war"),
    ("A warm reception greeted them.", "war"),
    ("He was a warden at the facility.", "war"),
    ("That is a straightforward answer.", "war"),
    ("Backwards compatibility matters.", "war"),
])
def test_innocent_words_do_not_match_high_scrutiny_terms(text, word):
    assert not C.matches_any(text, "high_scrutiny"), f"{word!r} matched inside {text!r}"


@pytest.mark.parametrize("text", [
    "Unsaid things matter most.",
    "A misstated figure was corrected.",
])
def test_innocent_words_do_not_count_as_attribution(text):
    assert not C.matches_any(text, "attribution")


# --- and the real matches that must survive ---------------------------------

@pytest.mark.parametrize("text", [
    "The war in Ukraine continued.",
    "Airbases were used for the operation.",      # plural
    "Repeated strikes were reported.",            # plural
    "An attack occurred on Tuesday.",
    "Allegations of fraud surfaced.",             # plural
    "The regime denied involvement.",
    "A nuclear facility was inspected.",
])
def test_genuine_high_scrutiny_terms_still_match(text):
    assert C.matches_any(text, "high_scrutiny"), text


@pytest.mark.parametrize("text", [
    "He said the figure was accurate.",
    "According to the ministry, exports rose.",
    "Sources said the deal was signed.",
    "The report stated otherwise.",
    "Data from the census shows growth.",
])
def test_genuine_attribution_still_matches(text):
    assert C.matches_any(text, "attribution"), text


# --- the hard cap, which is what the bug actually broke ---------------------

@pytest.mark.parametrize("text", [
    "The warehouse manager claimed the new system improves delivery times.",
    "A forward-looking plan was claimed to cut costs by the operations team.",
    "Staff claimed the warm reception showed morale had improved.",
])
def test_innocent_business_copy_is_not_capped(text):
    """These were capped at 45 — a 40-point penalty — because "warehouse"
    contains "war" and the sentence used the word "claimed"."""
    fired = {c.code for c in rules.analyze(text, "T", "news_article").caps}
    assert "sensitive_allegation_unsourced" not in fired, text


@pytest.mark.parametrize("text", [
    "The Ministry is accused of massive fraud running into crores.",
    "Officials are accused of corruption and nobody has denied it.",
    "Pakistan allegedly provided its airbases for strikes against Iran.",
])
def test_genuine_unsourced_allegations_are_still_capped(text):
    fired = {c.code for c in rules.analyze(text, "T", "news_article").caps}
    assert "sensitive_allegation_unsourced" in fired, text


def test_sourced_allegations_remain_uncapped():
    """Tightening this must never suppress accountability reporting."""
    text = "According to a CAG audit, the Ministry is accused of misallocating funds."
    fired = {c.code for c in rules.analyze(text, "T", "news_article").caps}
    assert "sensitive_allegation_unsourced" not in fired


# --- the helper itself -------------------------------------------------------

def test_inflections_are_matched():
    """Moving to boundaries must not start missing plurals — the point is to
    stop "warehouse" matching "war", not to lose "airbases"."""
    for word in ("airbase", "airbases", "strike", "strikes", "striking"):
        assert C.matches_any(f"The {word} was noted.", "high_scrutiny"), word


def test_multiword_phrases_still_match():
    assert C.matches_any("According to the report, it rose.", "attribution")
    assert C.matches_any("Data from the survey confirms it.", "attribution")


def test_counting_is_whole_word_too():
    """count_matches feeds the sourcing score, so miscounting shifts a
    dimension."""
    assert C.count_matches("Unsaid, misstated, unstated.", "attribution") == 0
    assert C.count_matches("He said it. She said it too.", "attribution") == 2


def test_found_terms_reports_what_matched():
    found = C.found_terms("The war led to an attack.", "high_scrutiny")
    assert set(found) == {"war", "attack"}


def test_empty_input_is_safe():
    for value in ("", None):
        assert C.matches_any(value, "attribution") is False
        assert C.count_matches(value, "attribution") == 0
        assert C.found_terms(value, "attribution") == []


def test_every_registered_list_is_usable():
    for name in ("attribution", "bias", "high_scrutiny", "ai_cliches",
                 "opinion_as_fact"):
        C.matches_any("probe text", name)   # must not raise
