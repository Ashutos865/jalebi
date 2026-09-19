"""Fourth-round audit fixes: signal counting, figure extraction, empty blends.

Each was reproduced before being fixed.
"""
from __future__ import annotations

import pytest

from app.scoring import constitution as C, engine, reasoning
from app.scoring.engine import AIReport
from app.scoring.rules import _STAT


# --- reasoning signals must be counted once, and not as substrings ----------

@pytest.mark.parametrize("text,vocab", [
    ("Although the data is thin, exports rose.", reasoning.COUNTERPOINT),
    ("Nonetheless the figures held.", reasoning.COUNTERPOINT),
    ("Compared to last year, output rose.", reasoning.COMPARATIVE),
    ("Output rose, whereas imports fell.", reasoning.COMPARATIVE),
    ("It grew because of demand.", reasoning.CAUSAL),
])
def test_one_signal_counts_once(text, vocab):
    """`sum(haystack.count(n) for n in needles)` let several overlapping terms
    claim the same span, so "although" scored twice -- once as "although" and
    once as "though" -- and one concession earned double credit."""
    assert reasoning._count(text.lower(), vocab) == 1, text


@pytest.mark.parametrize("text,vocab", [
    ("As a precaution the ministry paused the scheme.", reasoning.COUNTERPOINT),
    ("The bus route was rethought.", reasoning.COUNTERPOINT),
    ("Sales were unyielding.", reasoning.COUNTERPOINT),
])
def test_substrings_are_not_reasoning_signals(text, vocab):
    """Seventh instance of this bug class: "caution" inside "precaution"."""
    assert reasoning._count(text.lower(), vocab) == 0, text


def test_genuine_multi_signal_sentences_still_add_up():
    """The fix must not collapse distinct signals into one."""
    text = "On the other hand, critics caution that it may not last."
    assert reasoning._count(text.lower(), reasoning.COUNTERPOINT) == 3


# --- statistics must be extracted whole -------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Inflation rose 5.5%.", ["5.5%"]),
    ("GDP grew 7.25 percent.", ["7.25 percent"]),
    ("Exports reached 12.7%.", ["12.7%"]),
    # "$1.5 million" matched twice, as "$1" and "5 million".
    ("Revenue hit $1.5 million.", ["$1.5 million"]),
    ("It cost $0.75 million.", ["$0.75 million"]),
    ("Growth of 1.05 crore units.", ["1.05 crore"]),
    # Whole numbers must be untouched by the decimal support.
    ("Exports rose 12%.", ["12%"]),
    ("A total of 1,200 people attended.", ["1,200 people"]),
])
def test_decimals_are_part_of_the_figure(text, expected):
    """The pattern matched the tail of a decimal rather than the number, so
    "5.5%" yielded "5%" -- a figure the writer never wrote."""
    assert [m.group(0) for m in _STAT.finditer(text)] == expected, text


# --- an absent AI score must not perturb the rules score --------------------

@pytest.mark.parametrize("rule_score", [58, 61, 63, 67, 72, 78, 83])
def test_rules_score_passes_through_when_the_model_is_silent(rule_score):
    """The fallback quantised rule_s to the nearest 5 and blended it with
    itself, so a dimension the model never mentioned drifted by up to a point.
    This is the whole no-API-key path."""
    rules_report = _rules_report({d.key: rule_score for d in C.DIMENSIONS})
    ai = AIReport(dim_scores={}, issues=[], strengths=[], weaknesses=[], summary="")

    composed = engine.combine(rules_report, ai, "analysis")
    for cat in composed.categories:
        assert cat.score == rule_score, f"{cat.key} drifted to {cat.score}"


def test_a_present_ai_score_is_still_blended():
    """The fix must not disable blending."""
    rules_report = _rules_report({d.key: 60 for d in C.DIMENSIONS})
    ai = AIReport(
        dim_scores={d.key: 90 for d in C.DIMENSIONS},
        issues=[], strengths=[], weaknesses=[], summary="",
    )

    composed = engine.combine(rules_report, ai, "analysis")
    for cat in composed.categories:
        assert 60 < cat.score < 90, f"{cat.key} was not blended: {cat.score}"


def _rules_report(dim_scores):
    from app.scoring.rules import RuleReport

    return RuleReport(dim_scores=dim_scores)
