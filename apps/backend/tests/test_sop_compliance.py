"""TIES Content SOP — mechanical compliance checks."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.scoring import sop_compliance as sc
from app.scoring import sop_header


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as c:   # `with` runs lifespan → tables created
        yield c

_SENT = (
    "India's merchandise exports rose sharply in FY24, according to Ministry data. "
)


def _doc(body: str, *, header: bool = True, refs: bool = True) -> str:
    head = (
        "WRITING FOR: TIES Website\n"
        "HEADING: India's export surge\n"
        "SUB-HEADING: What the numbers hide\n"
        "AUTHOR'S NAME: A Writer\n"
        "AUTHOR'S INSTAGRAM ID: @awriter\n"
        "EDITOR'S NAME: An Editor\n"
        "DATE OF ASSIGNMENT: 01/09/2026\n"
        "DATE OF SUBMISSION: 02/09/2026\n"
        "DATE OF EDITING: 03/09/2026\n\n"
        "(YOUR CONTENT STARTS HERE)\n\n"
    ) if header else ""
    tail = (
        "\n\nFOOTNOTES / LINKS TO ALL YOUR REFERENCES\nhttps://commerce.gov.in/r\n"
    ) if refs else ""
    return head + body + tail


def _run(text: str, ct: str = "analysis", **kw) -> sc.SopReport:
    h = sop_header.parse(text)
    return sc.evaluate(h, h.body or text, ct, **kw)


def _check(report: sc.SopReport, needle: str) -> sc.SopCheck:
    for c in report.checks:
        if needle.lower() in c.name.lower():
            return c
    raise AssertionError(f"no check matching {needle!r} in {[c.name for c in report.checks]}")


# --- word count -------------------------------------------------------------

def test_short_form_word_window_is_300_350():
    r = _run(_doc(_SENT * 5))          # ~60 words, well under
    c = _check(r, "word count")
    assert not c.passed and "expand" in c.detail


def test_word_count_in_range_passes():
    body = "## Section\n\n" + _SENT * 28   # ~310 words
    r = _run(_doc(body))
    c = _check(r, "word count")
    assert c.passed, c.detail
    assert 300 <= r.word_count <= 350


def test_over_limit_is_flagged_with_trim_amount():
    r = _run(_doc(_SENT * 60))
    c = _check(r, "word count")
    assert not c.passed and "trim" in c.detail


def test_long_form_has_no_word_window():
    """The SOP's 300-350 applies to short-form; long-form must not be capped."""
    r = _run(_doc(_SENT * 60), ct="research_paper")
    assert r.word_min is None and r.word_max is None
    assert not any("word count" in c.name.lower() for c in r.checks)


def test_explicit_assignment_window_overrides_default():
    r = _run(_doc(_SENT * 5), word_min=40, word_max=100)
    assert _check(r, "word count").passed


# --- header -----------------------------------------------------------------

def test_missing_header_is_blocking():
    r = _run(_doc(_SENT * 26, header=False))
    c = _check(r, "header block present")
    assert not c.passed and c.blocking


def test_missing_author_field_is_reported():
    doc = _doc(_SENT * 26).replace("AUTHOR'S INSTAGRAM ID: @awriter\n", "")
    c = _check(_run(doc), "author fields")
    assert not c.passed and "INSTAGRAM" in c.detail


def test_invalid_writing_for_is_rejected():
    doc = _doc(_SENT * 26).replace("WRITING FOR: TIES Website", "WRITING FOR: Medium")
    c = _check(_run(doc), "WRITING FOR")
    assert not c.passed and "Medium" in c.detail


def test_editor_fields_are_advisory_not_blocking():
    """An author must not be blocked on fields the editor fills in later."""
    doc = _doc(_SENT * 26).replace("EDITOR'S NAME: An Editor\n", "")
    c = _check(_run(doc), "editor fields")
    assert not c.passed and not c.blocking


# --- structure --------------------------------------------------------------

def test_flat_text_fails_subheading_check():
    r = _run(_doc(_SENT * 26))
    assert not _check(r, "subheading").passed


def test_markdown_subheadings_pass():
    body = "## The shift\n\n" + _SENT * 13 + "\n\n### Why it matters\n\n" + _SENT * 13
    assert _check(_run(_doc(body)), "subheading").passed


def test_bare_line_subheadings_pass():
    """Plain-text export loses markdown, so short standalone lines must count."""
    body = "The shift\n\n" + _SENT * 13 + "\n\nWhy it matters\n\n" + _SENT * 13
    assert _check(_run(_doc(body)), "subheading").passed


def test_bullets_detected_as_lists():
    body = "## S\n\n" + _SENT * 26 + "\n\n- First takeaway\n- Second takeaway\n"
    assert _check(_run(_doc(body)), "lists").passed


def test_numbered_lists_detected():
    body = "## S\n\n" + _SENT * 26 + "\n\n1. First\n2. Second\n"
    assert _check(_run(_doc(body)), "lists").passed


def test_missing_lists_is_advisory():
    assert not _check(_run(_doc(_SENT * 26)), "lists").blocking


# --- references -------------------------------------------------------------

def test_missing_references_is_blocking():
    c = _check(_run(_doc(_SENT * 26, refs=False)), "references section")
    assert not c.passed and c.blocking


def test_references_without_links_flagged():
    doc = _doc(_SENT * 26, refs=False) + "\n\nReferences\nMinistry of Commerce, 2024\n"
    c = _check(_run(doc), "references contain links")
    assert not c.passed


def test_reference_links_counted():
    c = _check(_run(_doc(_SENT * 26)), "references contain links")
    assert c.passed and "1 link" in c.detail


# --- report roll-up ---------------------------------------------------------

def test_fully_compliant_document_passes():
    body = (
        "## The shift\n\n" + _SENT * 15 +
        "\n\n### Why it matters\n\n" + _SENT * 15 +
        "\n\n- Exports up\n- Electronics led\n"
    )
    r = _run(_doc(body))
    assert r.compliant, [f"{c.name}: {c.detail}" for c in r.blocking_failures]
    assert r.failures == []


def test_non_compliant_document_reports_every_failure():
    r = _run(_doc(_SENT * 5, header=False, refs=False))
    names = {c.name for c in r.blocking_failures}
    assert "SOP header block present" in names
    assert "References section present" in names
    assert not r.compliant


# --- through the API --------------------------------------------------------

def _api_body(words_sent: int = 15) -> str:
    return _doc(
        "## The shift\n\n" + _SENT * words_sent +
        "\n\n### Why it matters\n\n" + _SENT * words_sent +
        "\n\n- Exports up\n- Electronics led\n"
    )


def test_evaluate_returns_sop_report(client):
    r = client.post(
        "/api/evaluate", json={"text": _api_body(), "content_type": "analysis"}
    )
    assert r.status_code == 200
    sop = r.json()["sop"]
    assert sop["checked"] is True
    assert sop["header_present"] is True
    assert sop["header_fields"]["author_name"] == "A Writer"
    assert sop["reference_urls"] == ["https://commerce.gov.in/r"]
    assert any(c["name"] == "SOP header block present" and c["passed"]
               for c in sop["checks"])


def test_non_sop_document_is_not_checked(client):
    """Most documents are not TIES assignments; a wall of red is noise."""
    r = client.post(
        "/api/evaluate",
        json={"text": _SENT * 40, "content_type": "analysis"},
    )
    sop = r.json()["sop"]
    assert sop["checked"] is False
    assert sop["checks"] == []


def test_assignment_word_window_is_honoured_by_the_api(client):
    r = client.post(
        "/api/evaluate",
        json={
            "text": _api_body(),
            "content_type": "analysis",
            "word_min": 10,
            "word_max": 5000,
        },
    )
    sop = r.json()["sop"]
    assert sop["word_min"] == 10 and sop["word_max"] == 5000
    assert all(c["passed"] for c in sop["checks"] if "Word count" in c["name"])


def test_sop_report_does_not_change_the_editorial_score(client):
    """Process compliance and writing quality stay separate concerns: failing SOP
    checks must not move the score."""
    body = _api_body()
    parsed = sop_header.parse(body)

    # Same article and same title, but one copy has the SOP wrapper. The wrapper
    # is metadata, so the editorial score must be identical.
    full = client.post(
        "/api/evaluate",
        json={"text": body, "content_type": "analysis"},
    ).json()
    bare = client.post(
        "/api/evaluate",
        json={
            "text": parsed.body,
            "content_type": "analysis",
            "title": parsed.get("heading"),   # the title the wrapper supplied
        },
    ).json()

    assert full["overall_score"] == bare["overall_score"]
    assert full["meta"]["word_count"] == bare["meta"]["word_count"]
    # The SOP verdict differs (bare doc has no header) while the score does not.
    assert full["sop"]["checked"] and not bare["sop"]["checked"]
