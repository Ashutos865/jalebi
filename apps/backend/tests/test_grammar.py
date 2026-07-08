"""Grammar engine tests (heuristic fallback) + /api/check endpoint."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.grammar.heuristic import check as hcheck
from app.main import app

client = TestClient(app)


def _rules(text):
    return {i.rule for i in hcheck(text)}


def test_detects_typo_with_offset():
    issues = hcheck("I will recieve it.")
    typo = next(i for i in issues if i.rule == "TYPO")
    assert typo.replacements == ["receive"]
    # offset points at the misspelled word
    assert "I will recieve it.".find("recieve") == typo.offset


def test_repeated_word_and_double_space():
    assert "REPEATED_WORD" in _rules("the the cat")
    assert "DOUBLE_SPACE" in _rules("hello  world")


def test_capitalization_and_i():
    assert "LOWERCASE_I" in _rules("yesterday i left.")
    assert "SENT_START_CAP" in _rules("Done. next point.")


def test_missing_space_after_punct():
    assert "MISSING_SPACE_AFTER_PUNCT" in _rules("Hello,world.")


def test_clean_text_has_no_issues():
    assert hcheck("The quick brown fox jumps over the lazy dog.") == []


def test_check_endpoint():
    r = client.post("/api/check", json={"text": "I will recieve teh package."})
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "heuristic"
    assert len(body["issues"]) >= 2
    assert all("offset" in i and "replacements" in i for i in body["issues"])


def test_check_empty():
    r = client.post("/api/check", json={"text": "   "})
    assert r.status_code == 200
    assert r.json()["issues"] == []
