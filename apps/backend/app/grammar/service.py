"""Grammar service — picks the engine (LanguageTool if configured, else heuristic)."""
from __future__ import annotations

from app.grammar import heuristic, languagetool
from app.schemas.grammar import CheckResponse


async def check(text: str, language: str = "en-US") -> CheckResponse:
    text = text or ""
    if not text.strip():
        return CheckResponse(issues=[], engine="none", language=language)
    if languagetool.is_configured():
        try:
            issues = await languagetool.check(text, language)
            return CheckResponse(issues=issues, engine="languagetool", language=language)
        except Exception:
            pass  # fall back to heuristic if the LT server is unreachable
    return CheckResponse(issues=heuristic.check(text), engine="heuristic", language=language)
