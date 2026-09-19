"""The TIES Content SOP vs the Editorial Constitution on short-form pieces.

Two Constitution rules contradict the SOP and must not apply to short-form:
  * the bullet-list penalty — the SOP *mandates* bulleted key takeaways
  * the 800/1500-word depth reward — the SOP caps short-form at ~350 words
Long-form keeps both. Before this was scoped, an SOP-perfect article scored
strictly worse than one that ignored the SOP.
"""
from __future__ import annotations

from app.scoring import constitution as C
from app.scoring import rules

_PARA = (
    "India's merchandise exports rose 12.7% in FY24, according to Ministry of "
    "Commerce data. The gain was led by electronics, a sector that barely "
    "registered a decade ago. Analysts at the RBI note the strategic shift was "
    "supported by the PLI scheme. Economists caution that global demand remains "
    "uncertain going into the next cycle. "
)
_TAKEAWAYS = (
    "\n\n- Exports up 12.7% in FY24"
    "\n- Electronics led the gain"
    "\n- PLI scheme underwrote the shift"
    "\n- Global demand remains the key risk"
    "\n- Watch European order books"
    "\n- Rupee stability matters\n"
)
SOP_PERFECT = _PARA * 6 + _TAKEAWAYS      # ~340 words + bulleted takeaways
LONG_PROSE = _PARA * 24                   # long, unbulleted


def _writing(text: str, ct: str) -> int:
    return rules.analyze(text, "India's export surge", ct).dim_scores["writing"]


def _depth(text: str, ct: str) -> int:
    return rules.analyze(text, "India's export surge", ct).dim_scores["depth"]


# --- classification ---------------------------------------------------------

def test_sop_types_are_short_form():
    for ct in ("breaking_news", "analysis", "opinion"):
        assert C.is_short_form(ct), ct


def test_longform_types_are_not_short_form():
    for ct in ("research_paper", "investigative", "case_study", "news_article"):
        assert not C.is_short_form(ct), ct


# --- bullets ----------------------------------------------------------------

def test_short_form_is_not_penalised_for_bulleted_takeaways():
    """The SOP requires them, so requiring them must not cost writing quality."""
    assert _writing(SOP_PERFECT, "analysis") == 100


def test_long_form_still_prefers_flowing_prose():
    """The Constitution's preference is correct for long-form and is preserved."""
    assert _writing(SOP_PERFECT, "research_paper") < 100


# --- length -----------------------------------------------------------------

def test_short_form_gets_no_length_reward():
    """An 800+ word bonus would push writers past their own 350-word brief.

    Asserts the *absence of a length bonus*, not exact equality: depth is now
    density-based (app/scoring/reasoning.py), so two different texts can differ
    by a point or two on their reasoning content alone. What must not happen is
    the long version scoring materially higher for being long.
    """
    long_score = _depth(LONG_PROSE, "analysis")
    short_score = _depth(SOP_PERFECT, "analysis")
    assert long_score - short_score < 5, (
        f"short-form appears to reward length: {short_score} -> {long_score}"
    )


def test_long_form_still_rewards_depth_with_length():
    assert _depth(LONG_PROSE, "research_paper") > _depth(SOP_PERFECT, "research_paper")


# --- the regression this whole module exists for ----------------------------

def test_sop_compliance_is_never_scored_below_sop_violation():
    """A writer who follows the SOP must not be marked down relative to one who
    ignores it, on any short-form type."""
    for ct in ("breaking_news", "analysis", "opinion"):
        assert _writing(SOP_PERFECT, ct) >= _writing(LONG_PROSE, ct), ct
        assert _depth(SOP_PERFECT, ct) >= _depth(LONG_PROSE, ct), ct
