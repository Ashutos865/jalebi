"""POST /api/check — real-time grammar/style check for the inline extension."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import maybe_require_auth
from app.config import settings
from app.grammar.service import check as run_check
from app.schemas.grammar import CheckRequest, CheckResponse

router = APIRouter(tags=["grammar"])


@router.post("/check", response_model=CheckResponse)
async def check(body: CheckRequest, _=Depends(maybe_require_auth)) -> CheckResponse:
    if len(body.text) > settings.max_document_chars:
        raise HTTPException(413, "Text too long for inline checking.")
    return await run_check(body.text, body.language)
