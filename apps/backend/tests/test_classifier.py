"""Content-type auto-classifier tests."""
from __future__ import annotations

from app.pipeline.classifier import classify


def test_press_release():
    r = classify("FOR IMMEDIATE RELEASE\n\nTIES announced today a new initiative. "
                 "Media contact: press@ties.org.\n###")
    assert r["content_type"] == "press_release"
    assert r["confidence"] > 0.2


def test_research_paper():
    r = classify("Abstract\n\nThis paper presents a methodology. Our hypothesis is "
                 "tested against the literature review. See references (Smith et al.).")
    assert r["content_type"] == "research_paper"


def test_twitter_thread():
    r = classify("🧵 1/ Here's why exports matter.\n2/ First point.\n3/ Second point.")
    assert r["content_type"] == "twitter_thread"


def test_empty_signal_defaults_to_news():
    r = classify("The quick brown fox jumped over lazy dogs near the river bank.")
    assert r["content_type"] == "news_article"
    assert r["confidence"] <= 0.5


def test_confidence_bounded():
    r = classify("According to officials, the minister said on Monday it was reported.")
    assert 0.0 <= r["confidence"] <= 0.95
