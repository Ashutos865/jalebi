"""One phrase, one charge per dimension -- and distinct findings read as such.

"Needless to say" appears in BIAS_PHRASES, AI_CLICHES and reasoning's FILLER.
Each list is legitimate on its own, but the writer was charged separately by
each, so the penalty depended on how many lists happened to contain a phrase
rather than on how bad it was.
"""
from __future__ import annotations

import pytest

from app.scoring import constitution as C
from app.scoring import rules
from app.scoring.reasoning import FILLER

BASE = "The ministry said exports rose 12% in FY24 according to official data. " * 8


def _scores(extra: str = ""):
    return rules.analyze(BASE + extra, "Exports rise", "analysis").dim_scores


def _issues(extra: str = ""):
    return rules.analyze(BASE + extra, "Exports rise", "analysis").issues


@pytest.mark.parametrize("phrase", ["needless to say", "everyone knows"])
def test_a_phrase_on_two_lists_is_not_charged_twice_to_writing(phrase):
    """These are on both the bias and cliche lists. The cliche rule already
    makes the prose complaint, so writing must charge once."""
    clean = _scores()["writing"]
    dirty = _scores(f" {phrase.capitalize()}, this is the best outcome available.")["writing"]

    # A single cliche is -10. Charging bias on top made it -15.
    assert clean - dirty <= 10, (
        f"'{phrase}' cost writing {clean - dirty} points across two lists"
    )


def test_a_bias_phrase_that_is_not_a_cliche_still_costs_writing():
    """The dedupe must not stop bias-only phrases being penalised at all."""
    clean = _scores()["writing"]
    dirty = _scores(" This is undeniably the best outcome available to anyone.")["writing"]
    assert dirty < clean, "a bias phrase stopped costing anything"


def test_accuracy_still_charges_for_every_bias_phrase():
    """Asserting certainty without evidence is a different fault from writing a
    tired phrase, so accuracy keeps its own charge."""
    clean = _scores()["accuracy"]
    dirty = _scores(" Needless to say, this is the best outcome available.")["accuracy"]
    assert dirty < clean


def test_the_reasoning_findings_have_distinct_titles():
    """Three different observations all carried the title "Reasoning gap", so
    the report showed one heading three times and read as a single complaint
    repeated."""
    issues = [i for i in _issues(" Needless to say, this is the best outcome.")
              if i.dim == "insight"]
    assert len(issues) > 1, "expected several reasoning findings"

    titles = [i.problem for i in issues]
    assert len(set(titles)) == len(titles), f"repeated titles: {titles}"


def test_every_reasoning_note_gets_a_real_title():
    """A note with no mapping falls back to the generic title; none of the
    notes the analyser actually produces should need it."""
    issues = [i for i in _issues(" Needless to say, this is the best outcome.")
              if i.dim == "insight"]
    assert all(i.problem != "Reasoning gap" for i in issues), \
        [i.problem for i in issues]


# --- whole-word matching, eighth instance of this bug class -----------------

@pytest.mark.parametrize("word", ["clearly", "always", "never"])
def test_cliche_and_bias_terms_do_not_match_inside_words(word):
    """`p in low` matched substrings. Whole-word matching is the rule
    everywhere else in this codebase."""
    import re
    # A longer word that contains the term.
    carrier = {"clearly": "unclearly", "always": "hallways", "never": "nevertheless"}[word]
    assert not re.search(rf"\b{word}\b", carrier), "test fixture is wrong"

    clean = _scores()["writing"]
    dirty = _scores(f" The schedule was {carrier} arranged for the review.")["writing"]
    assert dirty >= clean - 2, f"'{carrier}' was penalised for containing '{word}'"
