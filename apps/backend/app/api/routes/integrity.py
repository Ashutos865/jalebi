"""POST /api/integrity — research-integrity analysis (claims, citations, bias)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import maybe_require_auth
from app.analysis.analyzers import analyze_integrity

router = APIRouter(tags=["integrity"])


class IntegrityIn(BaseModel):
    text: str


@router.post("/integrity")
async def integrity(body: IntegrityIn, _=Depends(maybe_require_auth)) -> dict:
    text = body.text.strip()
    if not text:
        raise HTTPException(422, "Document text is empty.")
    report = analyze_integrity(text)
    return {
        "integrity_score": report.integrity_score,
        "citation_density": report.citation_density,
        "claims": report.claims[:50],
        "findings": [asdict(f) for f in report.findings[:100]],
    }
