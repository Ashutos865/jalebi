"""POST /api/classify — guess the content type so writers don't have to pick."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import maybe_require_auth
from app.pipeline.classifier import classify
from app.schemas.content_labels import label_for
from app.schemas.evaluation import ContentType

router = APIRouter(tags=["classify"])


class ClassifyIn(BaseModel):
    text: str
    title: str = ""


@router.post("/classify")
async def classify_route(body: ClassifyIn, _=Depends(maybe_require_auth)) -> dict:
    text = body.text.strip()
    if not text:
        raise HTTPException(422, "Document text is empty.")
    result = classify(text, body.title)
    ct = ContentType(result["content_type"])
    result["label"] = label_for(ct)
    return result
