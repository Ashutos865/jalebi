"""POST /api/classify — guess the content type so writers don't have to pick."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import maybe_require_auth
from app.pipeline.classifier import classify
from app.schemas.content_labels import label_for
from app.schemas.evaluation import ClassifyResponse, ContentType

router = APIRouter(tags=["classify"])


class ClassifyIn(BaseModel):
    text: str
    title: str = ""


# response_model, not `-> dict`: the extension's ClassifyResponse asserted a
# shape nothing on this side enforced, so a change here could silently break the
# sidebar. FastAPI now validates the response and documents it in the schema.
@router.post("/classify", response_model=ClassifyResponse)
async def classify_route(
    body: ClassifyIn, _=Depends(maybe_require_auth)
) -> ClassifyResponse:
    text = body.text.strip()
    if not text:
        raise HTTPException(422, "Document text is empty.")
    result = classify(text, body.title)
    ct = ContentType(result["content_type"])
    return ClassifyResponse(
        content_type=ct,
        confidence=result["confidence"],
        label=label_for(ct),
        scores=result.get("scores") or {},
    )
