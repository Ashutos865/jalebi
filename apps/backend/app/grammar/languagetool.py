"""LanguageTool client — the specialized grammar/style engine.

LanguageTool is a mature open-source checker (thousands of rules, many languages).
Run it via Docker (see docker-compose.yml) and set JALEBI_LANGUAGETOOL_URL; this
client normalizes its response into Jalebi's GrammarIssue shape.
"""
from __future__ import annotations

from typing import List

import httpx

from app.config import settings
from app.schemas.grammar import GrammarIssue

# LanguageTool issueType → Jalebi severity.
_SEVERITY = {
    "misspelling": "spelling",
    "typographical": "punctuation",
    "whitespace": "punctuation",
    "grammar": "grammar",
    "style": "style",
    "duplication": "grammar",
    "uncategorized": "style",
}


def is_configured() -> bool:
    return bool(settings.languagetool_url)


async def check(text: str, language: str = "en-US") -> List[GrammarIssue]:
    url = settings.languagetool_url.rstrip("/") + "/v2/check"
    async with httpx.AsyncClient(timeout=8) as client:
        resp = await client.post(url, data={"text": text, "language": language})
        resp.raise_for_status()
        data = resp.json()

    issues: List[GrammarIssue] = []
    for m in data.get("matches", []):
        rule = m.get("rule", {}) or {}
        issue_type = (rule.get("issueType") or "uncategorized").lower()
        cat = (rule.get("category", {}) or {}).get("name", "")
        ctx = (m.get("context", {}) or {}).get("text", "")
        issues.append(GrammarIssue(
            offset=m.get("offset", 0),
            length=m.get("length", 0),
            message=m.get("message", ""),
            short=m.get("shortMessage", ""),
            replacements=[r.get("value", "") for r in m.get("replacements", [])][:6],
            rule=rule.get("id", ""),
            category=cat,
            severity=_SEVERITY.get(issue_type, "style"),
            context=ctx,
        ))
    return issues
