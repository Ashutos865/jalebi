"""Fact-check worklist (SOP §4 "Compulsory Fact-Checking").

Jalebi surfaces and ranks what needs verifying; the editor still clicks every
link. Under-listing a claim is the dangerous failure here — an editor never
sees it — so detection is deliberately broad.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.analysis import factcheck


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def _claims(text: str):
    return {i.claim: i for i in factcheck.build(text).items}


# --- sentence splitting (the bug that hid statistics) ------------------------

def test_decimals_do_not_split_sentences():
    """A naive [^.!?]+ split turned '12.7%' into two fragments, so the
    statistic was never detected as a claim at all."""
    s = factcheck._sentences("Exports rose 12.7% in FY24. Electronics led.")
    assert s[0] == "Exports rose 12.7% in FY24."
    assert len(s) == 2


def test_urls_do_not_split_sentences():
    s = factcheck._sentences("Per data (https://commerce.gov.in/report), it rose.")
    assert len(s) == 1


def test_abbreviations_do_not_split_sentences():
    s = factcheck._sentences("Dr. Rao said exports rose. The trend held.")
    assert len(s) == 2


# --- claim detection ---------------------------------------------------------

def test_percentage_is_detected():
    assert any("12.7%" in c for c in _claims("Exports rose 12.7% in FY24 overall."))


def test_indian_number_words_detected():
    for phrase in ["45 crore", "3 lakh", "2 billion"]:
        text = f"The programme cost {phrase} according to officials."
        assert _claims(text), phrase


def test_fiscal_year_forms_detected():
    for fy in ["FY24", "FY2024", "FY23-24"]:
        assert _claims(f"Exports grew strongly in {fy} across every sector."), fy


def test_quotation_detected():
    text = '"The trend is encouraging but fragile," said one economist.'
    assert _claims(text)


def test_named_institution_detected():
    assert _claims("The Ministry of Commerce revised its export projections again.")


def test_short_fragments_are_not_claims():
    assert factcheck.build("It rose. Yes. Indeed.").total_claims == 0


# --- risk ranking ------------------------------------------------------------

def test_uncited_statistic_is_high_risk():
    item = next(iter(_claims("Exports rose 12.7% in FY24 across all sectors.").values()))
    assert item.risk == factcheck.RISK_HIGH
    assert "no linked source" in item.reason


def test_uncited_quotation_is_high_risk():
    text = '"The trend is encouraging but fragile," said one trade economist.'
    item = next(iter(_claims(text).values()))
    assert item.risk == factcheck.RISK_HIGH


def test_statistic_on_a_low_tier_source_is_high_risk():
    text = "A blog post claimed exports hit 45 crore last month overall."
    item = next(iter(_claims(text).values()))
    assert item.risk == factcheck.RISK_HIGH


def test_cited_statistic_is_lower_risk_than_uncited():
    cited = factcheck.build(
        "Exports rose 12.7% in FY24 (https://commerce.gov.in/report) overall."
    ).items[0]
    uncited = factcheck.build("Exports rose 12.7% in FY24 overall.").items[0]
    order = {"high": 0, "medium": 1, "low": 2}
    assert order[cited.risk] > order[uncited.risk]


def test_items_are_sorted_high_risk_first():
    text = (
        "According to Ministry of Commerce data (https://commerce.gov.in/r), trade grew.\n"
        "Exports rose 12.7% in FY24 with no source at all.\n"
    )
    risks = [i.risk for i in factcheck.build(text).items]
    assert risks[0] == factcheck.RISK_HIGH


def test_citation_in_the_following_sentence_is_found():
    """Footnote-style sourcing puts the link on the next line."""
    text = (
        "Exports rose 12.7% in FY24 across every major sector.\n"
        "See https://commerce.gov.in/report for the full dataset.\n"
    )
    item = factcheck.build(text).items[0]
    assert item.citation == "https://commerce.gov.in/report"


def test_uncited_count_is_accurate():
    text = (
        "Exports rose 12.7% in FY24 overall.\n"
        "Imports fell 3% per data at https://commerce.gov.in/r this year.\n"
    )
    wl = factcheck.build(text)
    assert wl.total_claims == 2 and wl.uncited_claims == 1


def test_empty_text_is_safe():
    wl = factcheck.build("")
    assert wl.items == [] and wl.total_claims == 0


# --- endpoint ----------------------------------------------------------------

def test_factcheck_endpoint(client):
    r = client.post(
        "/api/factcheck",
        json={"text": "Exports rose 12.7% in FY24 across every major sector."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total_claims"] == 1
    assert body["high_risk_count"] == 1
    assert body["items"][0]["verified"] is False   # the editor ticks this


def test_factcheck_ignores_the_sop_header(client):
    """Metadata is not prose, so header lines must not become claims."""
    doc = (
        "WRITING FOR: TIES Website\nHEADING: Exports\nSUB-HEADING: FY24\n"
        "AUTHOR'S NAME: A Writer\nDATE OF ASSIGNMENT: 01/09/2026\n\n"
        "(YOUR CONTENT STARTS HERE)\n\n"
        "Exports rose 12.7% in FY24 across every major sector.\n"
    )
    body = client.post("/api/factcheck", json={"text": doc}).json()
    assert body["total_claims"] == 1
    assert "WRITING FOR" not in body["items"][0]["claim"]


def test_empty_text_rejected(client):
    assert client.post("/api/factcheck", json={"text": "   "}).status_code == 422
