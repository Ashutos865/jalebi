"""Grammar-checker precision.

A wrong suggestion is worse than a missing one: it appears inline as the writer
types, and accepting it actively damages correct prose. These pin the three
verified false-positive classes.
"""
from __future__ import annotations

import pytest

from app.grammar import heuristic


def _rules(text: str, rule: str):
    return [i for i in heuristic.check(text) if i.rule == rule]


# --- a/an: English selects by sound, not spelling ---------------------------

@pytest.mark.parametrize("text", [
    "I went to a university last year.",
    "It was a one-off event entirely.",
    "She met a European envoy today.",
    "He gave a unanimous verdict here.",
    "This is a useful distinction now.",
])
def test_vowel_letters_with_consonant_sounds_are_not_flagged(text):
    assert _rules(text, "A_AN") == [], text


@pytest.mark.parametrize("text", [
    "It took an hour to finish.",
    "He joined an FBI taskforce.",
    "They filed an MP complaint form.",
    "She is an honest broker here.",
    "He was an heir to the estate.",
    "It needs an X-ray immediately.",
])
def test_consonant_letters_with_vowel_sounds_are_not_flagged(text):
    assert _rules(text, "A_AN") == [], text


@pytest.mark.parametrize("word", [
    "unusual", "unexpected", "understanding", "umbrella", "uncle",
])
def test_un_words_with_vowel_sounds_are_still_flagged(word):
    """The 'uni-/una-' exceptions must not swallow ordinary 'un-' words, which
    genuinely take 'an'."""
    assert _rules(f"It was a {word} case.", "A_AN"), word


@pytest.mark.parametrize("text,expected", [
    ("I saw a elephant today.", "an"),
    ("She ate an banana quickly.", "a"),
    ("It was a obvious mistake.", "an"),
])
def test_real_agreement_errors_are_still_caught(text, expected):
    hits = _rules(text, "A_AN")
    assert hits, text
    assert expected in hits[0].replacements


def test_initialism_detection_ignores_ordinary_capitalised_words():
    """'Ministry' is capitalised but not read letter by letter."""
    assert heuristic._is_initialism("FBI") is True
    assert heuristic._is_initialism("MP") is True
    assert heuristic._is_initialism("Ministry") is False
    assert heuristic._is_initialism("A") is False


# --- punctuation must not fire inside URLs or decimals ----------------------

@pytest.mark.parametrize("text", [
    "See https://commerce.gov.in/report for the data.",
    "Visit www.example.com/page now.",
    "Email desk@ties.org for details.",
    "Exports rose 12.7% in FY24 overall.",
    "The figure was 3.5 billion rupees.",
])
def test_no_missing_space_inside_urls_and_decimals(text):
    assert _rules(text, "MISSING_SPACE_AFTER_PUNCT") == [], text


def test_genuinely_missing_space_is_still_caught():
    assert _rules("Hello.World is here.", "MISSING_SPACE_AFTER_PUNCT")


# --- the fix must not delete paragraph structure ----------------------------

def test_space_before_punctuation_does_not_span_newlines():
    """\\s+ matched newlines, so accepting the fix replaced a paragraph break
    with the punctuation mark and silently destroyed the writer's structure."""
    assert _rules("The end of a line\n\n, and a new paragraph.",
                  "SPACE_BEFORE_PUNCT") == []


def test_space_before_punctuation_is_still_caught_inline():
    hits = _rules("This is wrong , obviously.", "SPACE_BEFORE_PUNCT")
    assert hits


# --- applying every suggestion must never corrupt correct prose -------------

def test_a_clean_paragraph_yields_no_high_confidence_fixes():
    clean = (
        "India's merchandise exports rose 12.7% in FY24, according to Ministry "
        "of Commerce data (https://commerce.gov.in).\n\n"
        "It took an hour to compile, and a university team verified the figures "
        "for an FBI-style audit trail."
    )
    bad = {"A_AN", "MISSING_SPACE_AFTER_PUNCT", "SPACE_BEFORE_PUNCT"}
    hits = [i.rule for i in heuristic.check(clean) if i.rule in bad]
    assert hits == [], hits
