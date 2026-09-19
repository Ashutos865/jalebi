"""Outbound notifications (Slack / Microsoft Teams).

All best-effort and env-gated — no webhook configured means a silent no-op, so the
evaluation path never depends on them.

"Never depends on them" covers failure, which is swallowed, but it did not cover
*latency*. Each webhook was posted in turn, inside the request, with an 8-second
timeout, so two hung webhooks added sixteen seconds to the user's response for a
message they never see. Sends now run concurrently and are handed to the caller
as a coroutine to schedule in the background, so the response does not wait on
them at all.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import settings
from app.schemas.evaluation import EvaluationRequest, EvaluationResult

log = logging.getLogger("jalebi")


async def _post(url: str, payload: dict) -> None:
    async with httpx.AsyncClient(timeout=8) as client:
        await client.post(url, json=payload)


async def _post_quietly(url: str, payload: dict) -> None:
    """One webhook. An outage must never fail the caller's operation, but it
    should not vanish without trace either."""
    try:
        await _post(url, payload)
    except Exception as exc:
        log.warning("Webhook post failed (%s): %s", url.split("/")[2] if "/" in url else url, exc)


async def _fan_out(text: str) -> None:
    """Post to every configured webhook at once.

    Concurrent, not sequential: two webhooks used to cost the sum of their
    timeouts rather than the longer of the two.
    """
    urls = [u for u in (settings.slack_webhook_url, settings.teams_webhook_url) if u]
    if not urls:
        return
    payload = {"text": text}
    await asyncio.gather(*(_post_quietly(url, payload) for url in urls))


async def notify(text: str) -> None:
    """Send a plain message to every configured webhook.

    Best-effort and concurrent. Callers on a request path should schedule this
    with `BackgroundTasks` rather than awaiting it, so a slow webhook cannot
    delay the response.
    """
    await _fan_out(text)


def publication_ready_text(
    result: EvaluationResult, request: EvaluationRequest
) -> str:
    title = request.title or "Untitled"
    return (
        f"Jalebi: “{title}” is publication-ready — "
        f"{result.overall_score}/100 ({result.meta.evaluator}). "
        f"{len(result.strengths)} strengths, {len(result.critical_issues)} open issues."
    )


async def notify_publication_ready(
    result: EvaluationResult, request: EvaluationRequest
) -> None:
    await _fan_out(publication_ready_text(result, request))
