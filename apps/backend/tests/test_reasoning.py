"""Deterministic reasoning analysis — the no-API-key scoring path.

Jalebi must be useful with no key configured. Before this module, `insight`
returned a flat 60.0 (plus 8 for containing a word like "surprisingly"), so a
fifth of the score carried no information and an excellent analytical piece
scored the same as vacuous filler.
"""
from __future__ import annotations

import pytest

from app.scoring import constitution as C
from app.scoring import reasoning, rules
from app.schemas.evaluation import ContentType

STRONG = (
    "India's merchandise exports rose 12.7% in FY24, according to Ministry of "
    "Commerce data. The gain was driven by electronics, a sector that barely "
    "registered a decade ago. This suggests the PLI scheme worked less by "
    "subsidising output than by changing where firms located assembly, because "
    "the incentive was tied to incremental production. Compared with the 2018 "
    "cycle, the structural difference is that demand came from diversification "
    "rather than domestic consumption. However, economists caution that the "
    "underlying dependency on imported components means the trade balance "
    "improved less than headline figures imply. That explains why the rupee did "
    "not strengthen as it did in earlier export booms."
)

WEAK = (
    "Exports went up a lot this year. It was really good news for everyone "
    "involved. Many people are saying this is a big deal for the country going "
    "forward. The government has done a lot of work on this and it shows. At "
    "the end of the day, only time will tell what happens next. This is a game "
    "changer and will have a huge impact on the economy overall."
)


# --- the core requirement ---------------------------------------------------

def test_insight_separates_reasoning_from_filler():
    """The whole point: without a key, insight must still discriminate."""
    strong = reasoning.analyse(STRONG).insight
    weak = reasoning.analyse(WEAK).insight
    assert strong - weak >= 30, f"strong={strong} weak={weak}"


def test_depth_separates_explanation_from_assertion():
    assert reasoning.analyse(STRONG).depth - reasoning.analyse(WEAK).depth >= 20


def test_insight_is_no_longer_a_constant():
    """It returned 60.0 for every input that lacked nine specific phrases."""
    scores = {
        reasoning.analyse(t).insight
        for t in (STRONG, WEAK, "A short neutral sentence about exports.")
    }
    assert len(scores) == 3, f"scores collapsed: {scores}"


# --- individual signals -----------------------------------------------------

def test_inference_is_detected():
    s = reasoning.analyse("Exports rose. This suggests the scheme worked as intended.")
    assert s.inference >= 1


def test_causal_language_is_detected():
    s = reasoning.analyse("Output grew because the incentive was tied to production.")
    assert s.causal >= 1


def test_counterargument_is_rewarded():
    with_counter = reasoning.analyse(
        "Exports rose 12% in FY24 driven by electronics demand overseas. "
        "However, critics caution the underlying import dependency is unchanged."
    )
    without = reasoning.analyse(
        "Exports rose 12% in FY24 driven by electronics demand overseas. "
        "The sector grew steadily across every quarter of the year."
    )
    assert with_counter.counterpoint >= 1
    assert with_counter.insight > without.insight


def test_filler_is_penalised():
    s = reasoning.analyse(
        "This is a big deal. Many people are saying it is a game changer. "
        "At the end of the day, only time will tell."
    )
    assert s.filler >= 3
    assert s.insight < 50


def test_specifics_are_rewarded():
    specific = reasoning.analyse(
        "Exports rose 12.7% in FY24, per Ministry of Commerce data on trade."
    )
    vague = reasoning.analyse(
        "Exports rose quite a bit last year, according to the available data."
    )
    assert specific.specifics > vague.specifics


def test_claiming_insight_is_not_rewarded():
    """The old rule added 8 points for containing the word 'surprisingly'."""
    claimed = reasoning.analyse(
        "Surprisingly, it turns out this reveals a hidden counterintuitive truth."
    )
    reasoned = reasoning.analyse(
        "Output grew because the incentive targeted incremental production, "
        "which means firms relocated assembly rather than expanding capacity."
    )
    assert reasoned.insight > claimed.insight


# --- robustness -------------------------------------------------------------

@pytest.mark.parametrize("value", ["", "   ", None])
def test_empty_input_is_safe(value):
    s = reasoning.analyse(value)
    assert s.word_count == 0 and 0 <= s.insight <= 100


def test_scores_stay_in_range():
    for text in (STRONG, WEAK, "x", "Because " * 200, "Big deal! " * 100):
        s = reasoning.analyse(text)
        for score in (s.insight, s.depth, s.narrative):
            assert 0 <= score <= 100, (text[:20], score)


def test_repetition_cannot_game_the_score():
    """Every signal is density-capped, so padding does not inflate insight."""
    honest = reasoning.analyse(STRONG).insight
    spammed = reasoning.analyse(STRONG + " Therefore, this suggests. " * 50).insight
    assert spammed <= honest + 5


def test_analysis_is_deterministic():
    assert reasoning.analyse(STRONG).insight == reasoning.analyse(STRONG).insight


# --- integration with the scoring engine ------------------------------------

def test_rules_engine_uses_the_new_analysis():
    strong = rules.analyze(STRONG, "India exports rise", "analysis")
    weak = rules.analyze(WEAK, "Exports up", "analysis")
    assert strong.dim_scores["insight"] > weak.dim_scores["insight"] + 20
    assert strong.dim_scores["depth"] > weak.dim_scores["depth"]


def test_reasoning_gaps_become_actionable_issues():
    report = rules.analyze(WEAK, "Exports up", "analysis")
    assert any(i.dim == "insight" for i in report.issues)


def test_determinism_share_improved():
    """The rule share was raised because the rules improved, so verify the
    engine really is mostly deterministic now."""
    share = sum(
        C.DEFAULT_WEIGHTS[d.key] * d.alpha for d in C.DIMENSIONS
    )
    assert share >= 0.70, f"only {share:.0%} deterministic"


def test_every_content_type_is_mostly_deterministic():
    for ct in ContentType:
        w = C.weights_for(ct.value)
        share = sum(w[d.key] * d.alpha for d in C.DIMENSIONS)
        assert share >= 0.65, f"{ct.value}: {share:.0%}"
