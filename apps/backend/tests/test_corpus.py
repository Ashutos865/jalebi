"""Does the score match what an editor would say?

Every other test here pins a mechanism. This pins judgement: each corpus sample
declares the band an editor would place it in, written before the score was
computed, and the engine has to agree.

This is the only test file that has ever found a bug the unit tests could not.
Two, in fact — see test_accusing_an_institution_is_not_citing_it below.
"""
from __future__ import annotations

import asyncio

import pytest

from app.pipeline.hybrid_evaluator import HybridEvaluator
from app.schemas.evaluation import ContentType, EvaluationRequest
from app.scoring import rules
from tests.corpus import ALL, Sample


def _evaluate(sample: Sample):
    ev = HybridEvaluator(client=None, provider="mock", model="")
    return asyncio.run(
        ev.evaluate(
            EvaluationRequest(
                text=sample.text,
                content_type=ContentType(sample.content_type),
                title=sample.title,
            )
        )
    )


@pytest.mark.parametrize("sample", ALL, ids=lambda s: s.name)
def test_score_matches_editorial_judgement(sample: Sample):
    result = _evaluate(sample)
    low, high = sample.expect_band
    assert low <= result.overall_score <= high, (
        f"{sample.name}: scored {result.overall_score}, expected {low}-{high}.\n"
        f"An editor's reasoning: {sample.rationale}"
    )


@pytest.mark.parametrize(
    "sample", [s for s in ALL if s.expect_caps], ids=lambda s: s.name
)
def test_expected_hard_caps_fire(sample: Sample):
    report = rules.analyze(sample.text, sample.title, sample.content_type)
    fired = {c.code for c in report.caps}
    for code in sample.expect_caps:
        assert code in fired, (
            f"{sample.name}: expected the {code!r} cap. Fired: {sorted(fired)}"
        )


@pytest.mark.parametrize(
    "sample", [s for s in ALL if s.expect_weak], ids=lambda s: s.name
)
def test_weak_dimensions_score_low(sample: Sample):
    report = rules.analyze(sample.text, sample.title, sample.content_type)
    for key in sample.expect_weak:
        assert report.dim_scores[key] < 70, (
            f"{sample.name}: {key} scored {report.dim_scores[key]}, expected weak"
        )


@pytest.mark.parametrize(
    "sample", [s for s in ALL if s.expect_strong], ids=lambda s: s.name
)
def test_strong_dimensions_score_well(sample: Sample):
    report = rules.analyze(sample.text, sample.title, sample.content_type)
    for key in sample.expect_strong:
        assert report.dim_scores[key] >= 60, (
            f"{sample.name}: {key} scored {report.dim_scores[key]}, expected strong"
        )


def test_the_corpus_spans_the_range():
    """A corpus where everything scores the same would pass while proving
    nothing."""
    scores = [_evaluate(s).overall_score for s in ALL]
    assert max(scores) - min(scores) >= 25, f"corpus does not discriminate: {scores}"


def test_good_writing_outscores_bad():
    by_name = {s.name: _evaluate(s).overall_score for s in ALL}
    assert by_name["strong_analysis"] > by_name["weak_hype"]
    assert by_name["strong_analysis"] > by_name["padded_article"]
    assert by_name["competent_report"] > by_name["sensational_allegation"]
    assert by_name["padded_article"] > by_name["sensational_allegation"]


# --- the bugs this corpus found ---------------------------------------------

def test_accusing_an_institution_is_not_citing_it():
    """Found by the corpus, missed by 360 unit tests.

    "The Ministry is accused of fraud" registered as *sourced*, because
    "ministry" is a tier-1 source keyword. That disabled the hard cap written
    for exactly this sentence, and the article scored 63 instead of 45.
    """
    unsourced = "The Ministry is accused of massive fraud running into crores."
    fired = {c.code for c in rules.analyze(unsourced, "T", "breaking_news").caps}
    assert "sensitive_allegation_unsourced" in fired


@pytest.mark.parametrize("sentence", [
    "According to a CAG audit report, the Ministry is accused of misallocating funds.",
    "Reuters reported that officials were accused of fraud in the tender process.",
    "The Supreme Court judgment found the department accused of procedural corruption.",
])
def test_genuinely_sourced_allegations_are_not_capped(sentence):
    """The fix must not suppress legitimate accountability reporting — the whole
    point of the sourcing distinction."""
    fired = {c.code for c in rules.analyze(sentence, "T", "breaking_news").caps}
    assert "sensitive_allegation_unsourced" not in fired


def test_substring_matching_does_not_fake_attribution():
    """Also found here: "corruption" contains "pti", so an unsourced sentence
    counted as a Press Trust of India citation."""
    text = "Officials are accused of corruption and everyone knows it was rigged."
    fired = {c.code for c in rules.analyze(text, "T", "breaking_news").caps}
    assert "sensitive_allegation_unsourced" in fired
