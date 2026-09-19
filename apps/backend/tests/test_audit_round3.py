"""Third-round audit fixes: hearsay laundering and the fact-check risk ladder.

Both were reproduced before being fixed. The nation_first one inverts the
module's purpose: adding a fake attribution made a flag disappear.
"""
from __future__ import annotations

import pytest

from app.analysis import factcheck, nation_first


# --- anonymous hearsay must not launder unsourced disparagement -------------

@pytest.mark.parametrize("text", [
    "Sources say the Government is completely corrupt.",
    "Many people say the Indian Army has failed entirely.",
    "Some say Parliament is completely rigged.",
    "The Government is completely corrupt.",
])
def test_unsourced_disparagement_is_flagged(text):
    """_is_sourced accepted any attribution word, so "sources say" satisfied it
    while naming nobody. Prefixing a flagged sentence with "many people say"
    made the flag vanish -- the opposite of what this module is for."""
    assert nation_first.review(text).flags, text


@pytest.mark.parametrize("text", [
    "According to the CAG report, the Government scheme failed.",
    "The Supreme Court said the scheme was completely rigged.",
    "A Reuters investigation found the Government scheme was fraudulent.",
    "See https://cag.gov.in - the Government scheme failed.",
    # Whose sources they are is the distinction: an unqualified "sources said"
    # names nobody, "Ministry sources said" names an institution.
    "Ministry sources said the Government programme collapsed.",
])
def test_sourced_criticism_is_not_flagged(text):
    """Evidence-based accountability reporting is what the SOP asks for."""
    assert not nation_first.review(text).flags, text


# --- the fact-check worklist must rank by source quality --------------------

def _risk(text: str):
    items = factcheck.build(text).items
    assert items, f"no claim extracted from: {text}"
    return items[0].risk


@pytest.mark.parametrize("text", [
    "A popular blog reported that the new policy will reshape the export sector.",
    "A Twitter post reported that the new policy will reshape the export sector.",
    "A Substack opinion piece reported the policy reshapes the export sector.",
])
def test_low_tier_sources_outrank_credible_ones(text):
    """source_tier was recorded and then ignored for every claim without a
    figure, so a claim resting on a tweet sorted alongside one resting on a
    Supreme Court judgment."""
    assert _risk(text) != factcheck.RISK_LOW, text


@pytest.mark.parametrize("text", [
    "The Supreme Court judgment reported that the policy reshapes the sector.",
    "Reuters reported that the policy reshapes the export sector.",
    "The university study reported the policy reshapes the export sector.",
])
def test_credible_sources_stay_low_risk(text):
    assert _risk(text) == factcheck.RISK_LOW, text


def test_a_tweet_ranks_above_a_judgment_in_the_worklist():
    """The editor's list is ordered by what would hurt most if nobody looked."""
    text = (
        "The Supreme Court judgment reported that the policy reshapes the sector. "
        "A Twitter post reported that the new policy will reshape trade entirely."
    )
    items = factcheck.build(text).items
    assert len(items) == 2
    assert items[0].source_tier == 6, "the tweet should sort first"
