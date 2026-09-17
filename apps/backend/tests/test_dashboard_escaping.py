"""Dashboard XSS: user-controlled data must be escaped before innerHTML.

The dashboard builds its DOM with template literals. Document titles and URLs
come from /api/evaluate, which is unauthenticated by default, so a writer could
plant markup that executes in an *admin's* browser — a writer-to-admin
escalation. The page itself is a static constant, so this is client-side only,
but the impact if an admin opens the tab is a full session compromise.
"""
from __future__ import annotations

import re

from app.dashboard.views import _PAGE


def test_escaping_helpers_exist():
    assert "function esc(" in _PAGE
    assert "function safeUrl(" in _PAGE


def test_esc_covers_every_dangerous_character():
    for ch in ("&", "<", ">", '"', "'"):
        assert f"'{ch}'" in _PAGE or f'"{ch}"' in _PAGE, ch


def test_document_title_and_url_are_escaped():
    """The two sinks reachable from an unauthenticated /api/evaluate call."""
    assert "esc(d.title)" in _PAGE
    assert "safeUrl(d.url)" in _PAGE
    assert "${d.title}" not in _PAGE
    assert 'href="${d.url}"' not in _PAGE


def test_url_scheme_is_allow_listed():
    """javascript: and data: URLs must never reach an href."""
    assert "/^https?:\\/\\//i.test(s)" in _PAGE


def test_model_returned_text_is_escaped():
    """Issue text comes from the LLM and is prompt-injectable."""
    assert "esc(i.problem)" in _PAGE
    assert "${i.problem}" not in _PAGE


def test_user_and_audit_fields_are_escaped():
    for expr in ("esc(u.email)", "esc(r.actor", "esc(r.action)", "esc(r.target)"):
        assert expr in _PAGE, expr


def test_workflow_fields_are_escaped():
    for expr in ("esc(d.assigned_to", "esc(d.escalation_reason)",
                 "esc(d.override_reason)"):
        assert expr in _PAGE, expr


def test_no_unescaped_free_text_interpolation_remains():
    """Catch new sinks. Numbers and enum values computed server-side are fine;
    anything a user can type must go through esc()."""
    allowed = {
        # server-computed numerics
        "i.ai_percent", "i.plagiarism_percent", "r.avg_score", "r.count",
        "r.pass_rate",
        # validated against the ContentType enum before storage
        "r.content_type",
    }
    found = set(re.findall(
        r"\$\{(?!esc\(|safeUrl\()([a-z]\w*\.\w+)\}", _PAGE
    ))
    assert found <= allowed, f"unescaped interpolation: {sorted(found - allowed)}"
