"""Nation-First review queue (SOP §4 "Zero Tolerance for Anti-National Narratives").

The SOP demands zero tolerance for anti-national narratives *and* evidence-based
reporting. Those only conflict if you filter on topic, so this filters on
evidence: unsourced disparagement of a national institution is raised for the
editor; the same criticism with a source is not.

The most important tests here are the negative ones. A tool that flagged
well-sourced accountability journalism would suppress exactly the reporting the
SOP asks for, so those cases are pinned first.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.analysis import nation_first as nf


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def _flags(text: str):
    return nf.review(text).flags


# --- sourced criticism is never flagged (the one that matters) ---------------

@pytest.mark.parametrize("sentence", [
    "According to a CAG audit (https://cag.gov.in/report), the Government scheme "
    "failed to meet 60% of its targets.",
    "The Supreme Court held that the tender process was fraudulent, per its "
    "judgment of March 2024.",
    "Reuters reported that the policy collapsed within six months.",
    "Ministry of Finance data shows the programme failed to disburse 40% of funds.",
    "A peer-reviewed study found the scheme was largely ineffective for the country.",
])
def test_sourced_criticism_is_not_flagged(sentence):
    """Evidence-based accountability reporting is what the SOP requires."""
    assert _flags(sentence) == [], sentence


def test_naming_the_subject_is_not_the_same_as_citing_it():
    """'The Government is corrupt' must not count as *citing* the government —
    'government' is itself a tier-1 source keyword."""
    assert _flags("The Government is completely corrupt and failed the nation.")


# --- unsourced rhetoric is raised -------------------------------------------

def test_unsourced_disparagement_is_raised_for_review():
    flags = _flags("The Government is utterly corrupt and the country is collapsing.")
    assert flags and flags[0].severity == nf.SEVERITY_REVIEW
    assert "no source" in flags[0].reason


def test_unsourced_absolute_is_noted():
    flags = _flags("India has always lagged every other economy in this sector.")
    assert flags and flags[0].severity in (nf.SEVERITY_REVIEW, nf.SEVERITY_NOTE)


@pytest.mark.parametrize("subject", [
    "India", "the Government", "Parliament", "the Supreme Court",
    "the Army", "RBI", "ISRO", "the Election Commission",
])
def test_national_subjects_are_recognised(subject):
    assert _flags(f"{subject} is a complete disaster and utterly corrupt.")


# --- everything else is left alone ------------------------------------------

def test_neutral_reporting_is_not_flagged():
    assert _flags("The Government announced a new export scheme this week.") == []


def test_criticism_of_a_non_national_subject_is_not_flagged():
    """The mandate is about the nation, not about companies or individuals."""
    assert _flags("The startup failed completely and was a total disaster.") == []
    assert _flags("The company is corrupt and its accounts collapsed.") == []


def test_positive_claims_are_not_flagged():
    assert _flags("India has always led the world in this sector.") == []


def test_empty_text_is_safe():
    r = nf.review("")
    assert r.flags == [] and r.needs_review is False


# --- it must never touch the score ------------------------------------------

def test_review_does_not_affect_scoring(client):
    """Nation-First is a review queue, not a penalty. Flagged text must score
    exactly as it would otherwise."""
    flagged = "The Government is utterly corrupt and the country is collapsing. " * 8
    r = client.post(
        "/api/evaluate", json={"text": flagged, "content_type": "analysis"}
    )
    assert r.status_code == 200
    # No nation-first cap exists, so no cap code can appear in critical issues.
    labels = " ".join(i["problem"] for i in r.json()["critical_issues"])
    assert "nation" not in labels.lower()


# --- endpoint ---------------------------------------------------------------

def test_endpoint_returns_flags(client):
    r = client.post(
        "/api/nation-first",
        json={"text": "The Government is utterly corrupt and failed the nation."},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["needs_review"] is True
    assert body["flags"][0]["subject"]
    assert body["flags"][0]["has_source"] is False


def test_endpoint_clean_on_sourced_criticism(client):
    r = client.post(
        "/api/nation-first",
        json={
            "text": "According to a CAG audit (https://cag.gov.in/r), the "
                    "Government scheme failed to meet its targets."
        },
    )
    assert r.json()["needs_review"] is False
    assert r.json()["flags"] == []


def test_endpoint_ignores_the_sop_header(client):
    doc = (
        "WRITING FOR: TIES Website\nHEADING: A piece\nSUB-HEADING: S\n"
        "AUTHOR'S NAME: W\n\n(YOUR CONTENT STARTS HERE)\n\n"
        "The Government announced a new scheme this week.\n"
    )
    assert client.post("/api/nation-first", json={"text": doc}).json()["flags"] == []


def test_empty_text_rejected(client):
    assert client.post("/api/nation-first", json={"text": "  "}).status_code == 422
