"""POST /api/evaluate — run the editorial pipeline over a document."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import maybe_require_auth
from app.config import settings
from app.db.base import get_session
from app.db.models import User
from app.llm import registry
from app.pipeline import get_evaluator
from app.schemas.content_labels import label_for
from app.schemas.evaluation import ContentType, EvaluationRequest, EvaluationResult

router = APIRouter(tags=["evaluation"])


@router.get("/content-types")
async def content_types() -> list[dict]:
    """The content types the sidebar dropdown offers, with their rubric labels."""
    return [{"value": ct.value, "label": label_for(ct)} for ct in ContentType]


def _resolve_provider(requested: Optional[str]) -> str:
    if not requested:
        return settings.provider
    allowed = {p.id for p in registry.allowed_providers()}
    if requested not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Provider {requested!r} is not available. Choose: {sorted(allowed)}",
        )
    return requested


@router.post("/evaluate", response_model=EvaluationResult)
async def evaluate(
    request: EvaluationRequest,
    background: BackgroundTasks,
    user: Optional[User] = Depends(maybe_require_auth),
    session: AsyncSession = Depends(get_session),
) -> EvaluationResult:
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Document text is empty.")
    if len(text) > settings.max_document_chars:
        raise HTTPException(
            status_code=413,
            detail=f"Document exceeds {settings.max_document_chars} characters.",
        )
    # Rubric weights live in a per-process cache; resynchronise it from the DB
    # if this worker's copy has gone stale, so an admin's change reaches every
    # worker rather than only the one that served the write.
    from app.scoring import rubric_sync

    await rubric_sync.refresh_if_stale(session)

    provider = _resolve_provider(request.provider)
    result = await get_evaluator(provider).evaluate(request)

    # Persist to history (best-effort — never fail the evaluation over storage).
    try:
        from app.services.history import save_evaluation

        await save_evaluation(session, req=request, result=result, owner=user)
    except Exception:
        await session.rollback()

    # Notify on publication-ready (best-effort). Scheduled rather than awaited:
    # this used to post to each webhook in turn inside the request, so two hung
    # webhooks added sixteen seconds to the writer's response for a message
    # they never see.
    if settings.notify_on_ready and result.publication_ready:
        from app.integrations.notify import notify_publication_ready

        background.add_task(notify_publication_ready, result, request)

    return result
