"""A corpus of realistic articles with stated editorial expectations.

Everything else in this suite is a unit test: it pins a mechanism. This pins
*judgement* — whether the score a real editor would give matches the score
Jalebi gives.

Each entry declares the band an editor would place it in **before** the score is
computed, so the corpus tests a prior rather than rationalising whatever the
engine happens to produce. Where the engine disagrees, that is a finding to
investigate, not a test to loosen.

Bands (app/scoring/constitution.py):
    >= 85  Ready to Publish
    >= 75  Needs Minor Revision
    >= 60  Needs Major Revision
    <  60  Not Ready
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Sample:
    name: str
    content_type: str
    title: Optional[str]
    text: str
    #: Inclusive band an editor would expect, as (low, high).
    expect_band: tuple
    #: Why an editor would place it there.
    rationale: str
    #: Dimensions that should score notably well / badly, if any.
    expect_strong: List[str] = field(default_factory=list)
    expect_weak: List[str] = field(default_factory=list)
    #: Hard caps that should fire.
    expect_caps: List[str] = field(default_factory=list)


# ── 1. Well-sourced analysis. An editor would publish this with light edits. ──
STRONG_ANALYSIS = Sample(
    name="strong_analysis",
    content_type="analysis",
    title="Why India's export surge did not lift the rupee",
    expect_band=(75, 100),
    rationale=(
        "Every figure attributed to a named primary source, a mechanism "
        "explained rather than asserted, a counter-argument acknowledged, and a "
        "conclusion that follows from the evidence."
    ),
    expect_strong=["accuracy", "sourcing", "insight", "depth"],
    text="""India's merchandise exports rose 12.7% in FY24, according to Ministry of Commerce data released this week (https://commerce.gov.in/trade-statistics). The headline figure is the strongest in four years.

The gain was led by electronics, a sector that barely registered in the export basket a decade ago. This suggests the production-linked incentive scheme worked less by subsidising output than by changing where firms located final assembly, because the incentive was tied to incremental production rather than to installed capacity.

Compared with the 2018 cycle, the structural difference is that demand came from buyers diversifying away from China rather than from a weaker rupee. Analysts at the Reserve Bank of India note that the shift contributed roughly 3 percentage points to the overall gain.

However, economists caution that the underlying dependency on imported components means the trade balance improved considerably less than the headline implies. That explains why the rupee did not strengthen as it did during earlier export booms: the import bill rose alongside the export figure.

"The trend is encouraging but fragile," said one trade economist, pointing to slowing order books from European buyers in the final quarter.""",
)

# ── 2. Unsourced hype. No editor would publish this. ────────────────────────
WEAK_HYPE = Sample(
    name="weak_hype",
    content_type="analysis",
    title="Exports are booming and it's a huge deal",
    expect_band=(0, 65),
    rationale=(
        "Announces significance without supplying any. No figures, no sources, "
        "no mechanism, and filler in almost every sentence."
    ),
    expect_weak=["insight", "sourcing"],
    text="""Exports went up a lot this year and it was really good news for everyone involved in the sector.

Many people are saying this is a big deal for the country going forward, and at the end of the day it is hard to disagree with that assessment.

The government has clearly done a lot of work on this and it shows in the numbers, which are much better than before. This is a game changer.

Only time will tell what happens next, but the outlook seems very positive overall. Everyone knows that exports matter for growth, so this is obviously welcome news for the economy.""",
)

# ── 3. Sensational, unsourced allegation. Should be capped hard. ────────────
SENSATIONAL_ALLEGATION = Sample(
    name="sensational_allegation",
    content_type="breaking_news",
    title="SHOCKING: Ministry accused of massive fraud in export scheme",
    expect_band=(0, 60),
    rationale=(
        "A serious allegation against a named institution with no attribution "
        "at all. This is the case hard caps exist for."
    ),
    expect_weak=["accuracy", "sourcing"],
    # Only the allegation cap: the piece makes no numeric claim, so
    # unsupported_claim (which keys on unsourced statistics) correctly does not
    # apply. My first draft expected both, which was wrong about the rule.
    expect_caps=["sensitive_allegation_unsourced"],
    text="""SHOCKING revelations have emerged about the export incentive scheme, and you won't believe what officials have been hiding.

The Ministry is accused of massive fraud running into thousands of crores. Sources say the corruption goes right to the top and that officials deliberately manipulated the figures to look good.

Everyone knows the scheme was rigged from the start. The numbers were obviously fabricated to make the government look competent ahead of the election.

This is a total disaster for the country and proves the entire system is broken beyond repair.""",
)

# ── 4. Competent but ordinary reporting. Publishable, unremarkable. ─────────
COMPETENT_REPORT = Sample(
    name="competent_report",
    content_type="breaking_news",
    title="Exports rise 12.7% in FY24, ministry says",
    expect_band=(60, 90),
    rationale=(
        "Accurate, attributed, correctly structured news writing. It reports "
        "rather than analyses, so it should score respectably but not top."
    ),
    expect_strong=["accuracy", "sourcing"],
    text="""India's merchandise exports rose 12.7% in the 2024 financial year, according to data published by the Ministry of Commerce on Tuesday.

Exports reached $437 billion over the period, the ministry said. Electronics and pharmaceuticals accounted for the largest share of the increase.

The Reserve Bank of India said in its monthly bulletin that the figures were consistent with its earlier projections for the year.

A ministry spokesperson said the results reflected sustained demand from buyers in North America and Europe. Further detail is expected when the full trade statistics are released next month.""",
)

# ── 5. Opinion, well argued. Different weighting applies. ───────────────────
STRONG_OPINION = Sample(
    name="strong_opinion",
    content_type="opinion",
    title="The export numbers deserve more scepticism than they are getting",
    expect_band=(65, 95),
    rationale=(
        "Opinion weights insight highest. This argues a position, grounds it in "
        "cited figures and engages the counter-case, which is what the form asks."
    ),
    expect_strong=["insight"],
    text="""The celebration around this year's export figures has been remarkably uncritical, and that should worry anyone who reads trade data for a living.

The headline is real: exports rose 12.7% in FY24, per Ministry of Commerce data. But a headline figure measures gross value, not what the country retained, and those are very different questions when a third of the growth comes from assembly work whose components were imported the month before.

Compared with the export booms of 2011 and 2018, the domestic value-add per dollar shipped has fallen. That is the number worth arguing about, and almost nobody is publishing it.

Critics of this view make a fair point: assembly work builds capability, and capability compounds. Taiwan did not begin at the high end either. However, that argument requires the incentive structure to shift toward component manufacture over time, and there is no evidence in the current scheme design that it will.""",
)

# ── 6. Padded with filler around a genuine core. ────────────────────────────
PADDED_ARTICLE = Sample(
    name="padded_article",
    content_type="analysis",
    title="Understanding the export figures",
    expect_band=(50, 78),
    rationale=(
        "There is a real, attributed fact here, buried in padding. Should land "
        "below the genuinely analytical piece but above pure hype."
    ),
    expect_weak=["insight"],
    text="""In today's fast-paced world, trade figures matter more than ever before.

It is important to note that exports rose 12.7% in FY24, according to Ministry of Commerce data. This is a significant development.

Needless to say, there are many factors at play here, and it goes without saying that the situation is complex. A lot of people have opinions about what this means.

At the end of the day, the figures speak for themselves. Time will tell whether this trend continues, but for now it remains to be seen how the sector develops.

Moreover, furthermore, the implications are far-reaching and deserve careful consideration from all stakeholders involved in this important and evolving space.""",
)

# ── 7. Statistics with no attribution anywhere. ─────────────────────────────
UNSOURCED_STATS = Sample(
    name="unsourced_stats",
    content_type="analysis",
    title="The real export numbers",
    expect_band=(0, 70),
    rationale=(
        "Specific, confident, checkable figures with no source for any of them. "
        "Precisely the failure the unsupported-claim cap exists to catch."
    ),
    expect_weak=["accuracy", "sourcing"],
    expect_caps=["unsupported_claim"],
    text="""Exports rose 12.7% in FY24 to reach $437 billion, while imports climbed 9.3% over the same period.

Electronics contributed 3.1 percentage points of the total gain, and pharmaceuticals a further 1.8 points. The trade deficit narrowed to $78 billion.

Domestic value-add fell to 41% from 47% two years earlier. Component imports rose 22%, and assembly employment grew by 340,000 positions.

The rupee held at 83.2 despite the surplus, and forward contracts suggest the market expects little movement through the next quarter.""",
)

ALL: List[Sample] = [
    STRONG_ANALYSIS,
    WEAK_HYPE,
    SENSATIONAL_ALLEGATION,
    COMPETENT_REPORT,
    STRONG_OPINION,
    PADDED_ARTICLE,
    UNSOURCED_STATS,
]
