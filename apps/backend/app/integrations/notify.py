"""Outbound notifications (Slack / Microsoft Teams).

All best-effort and env-gated — no webhook configured means a silent no-op, so the
evaluation path never depends on them.
"""
from __future__ import annotations

import httpx

from app.config import settings
from app.schemas.evaluation import EvaluationRequest, EvaluationResult


async def _post(url: str, payload: dict) -> None:
    async with httpx.AsyncClient(timeout=8) as client:
        await client.post(url, json=payload)


async def notify_publication_ready(
    result: EvaluationResult, request: EvaluationRequest
) -> None:
    title = request.title or "Untitled"
    text = (
        f"📰 *Jalebi*: “{title}” is publication-ready — "
        f"{result.overall_score}/100 ({result.meta.evaluator}). "
        f"{len(result.strengths)} strengths, {len(result.critical_issues)} open issues."
    )
    if settings.slack_webhook_url:
        try:
            await _post(settings.slack_webhook_url, {"text": text})
        except Exception:
            pass
    if settings.teams_webhook_url:
        try:
            await _post(settings.teams_webhook_url, {"text": text})
        except Exception:
            pass
