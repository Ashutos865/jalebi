"""Tests for the deterministic TIES scoring engine.

Run in rules-only mode (client=None) so no model is needed: the engine falls back
to the deterministic rule scores, which is exactly what must be reproducible.
"""
import asyncio

from app.pipeline.hybrid_evaluator import HybridEvaluator
from app.scoring import constitution as C
from app.scoring import rules
from app.schemas.evaluation import ContentType, EvaluationRequest


def _score(text, title=None, content_type=ContentType.news_article):
    ev = HybridEvaluator(client=None, provider="mock", model="")
    req = EvaluationRequest(text=text, title=title, content_type=content_type)
    return asyncio.run(ev.evaluate(req))


CLEAN = (
    "According to a government report, manufacturing output rose last year. "
    "The ministry said the change reflected a shift in industrial policy. "
    "Analysts at a recognised institute noted the underlying incentive structure, "
    "explaining why firms responded the way they did. The consequence, they argued, "
    "was a slow but structural change in how the sector competes."
)


def test_weights_sum_to_one_per_content_type():
    for ct in ("breaking_news", "opinion", "analysis", "investigative", "news_article"):
        w = C.weights_for(ct)
        assert abs(sum(w.values()) - 1.0) < 0.001, (ct, sum(w.values()))
        assert set(w.keys()) == set(C.DIM_KEYS)


def test_determinism_identical_content_identical_score():
    a = _score(CLEAN, title="Manufacturing output and industrial policy")
    b = _score(CLEAN, title="Manufacturing output and industrial policy")
    assert a.overall_score == b.overall_score
    assert [c.score for c in a.categories] == [c.score for c in b.categories]


def test_unsourced_statistic_caps_score():
    text = "Nearly 45% of the population lost income last year and 2 million jobs vanished."
    res = _score(text, title="Economy in numbers")
    assert res.overall_score <= C.HARD_CAPS["unsupported_claim"].ceiling
    assert any("Hard rule" in i.problem for i in res.critical_issues)


def test_sensitive_allegation_without_source_caps_at_45():
    text = (
        "Pakistan allegedly provided its airspace and airbases to the USA for strikes "
        "against Iran. The accusation has spread widely and many now accept it as true."
    )
    res = _score(text, title="Airspace claims")
    assert res.overall_score <= C.HARD_CAPS["sensitive_allegation_unsourced"].ceiling


def test_ai_cliches_and_em_dash_penalise_writing():
    rep = rules.analyze(
        "In today's fast-paced world, it is worth noting the trend — clearly it matters.",
        None, "news_article",
    )
    assert rep.dim_scores["writing"] < 90
    problems = {i.problem for i in rep.issues}
    assert "AI cliché" in problems
    assert "Em dash used" in problems


def test_british_spelling_flagged():
    rep = rules.analyze("The color of the analyzed data.", None, "news_article")
    assert any(i.problem == "American spelling" for i in rep.issues)


def test_bias_phrase_flagged_and_neutrality_check_fails():
    rep = rules.analyze("Obviously this is the case and everyone knows it.", None, "news_article")
    assert any("absolutist" in i.problem.lower() for i in rep.issues)
    neutral = next(c for c in rep.checklist if c.name.startswith("Neutral"))
    assert neutral.passed is False


def test_explainability_present():
    res = _score(CLEAN, title="Manufacturing output and industrial policy")
    assert "Passed" in res.summary and "checks" in res.summary
    assert len(res.categories) == len(C.DIM_KEYS)
    assert res.publication_readiness is not None
