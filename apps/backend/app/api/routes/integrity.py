"""POST /api/integrity — research-integrity analysis (claims, citations, bias)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import maybe_require_auth
from app.analysis import factcheck
from app.analysis.analyzers import analyze_integrity
from app.scoring import sop_header

router = APIRouter(tags=["integrity"])


class IntegrityIn(BaseModel):
    text: str


@router.post("/integrity")
async def integrity(body: IntegrityIn, _=Depends(maybe_require_auth)) -> dict:
    text = body.text.strip()
    if not text:
        raise HTTPException(422, "Document text is empty.")
    # Grade the article, not the SOP metadata block.
    text = sop_header.scoring_text(text)
    report = analyze_integrity(text)
    return {
        "integrity_score": report.integrity_score,
        "citation_density": report.citation_density,
        "claims": report.claims[:50],
        "findings": [asdict(f) for f in report.findings[:100]],
    }


@router.post("/factcheck")
async def factcheck_list(body: IntegrityIn, _=Depends(maybe_require_auth)) -> dict:
    """The editor's fact-check worklist (SOP §4).

    Every checkable claim with its nearest citation, ranked by how badly it
    needs verification. This is a worklist, not a verdict: Jalebi does not fetch
    URLs or decide whether a source supports a claim — the SOP assigns that to
    the editor, who must click each link themselves.
    """
    text = body.text.strip()
    if not text:
        raise HTTPException(422, "Document text is empty.")
    worklist = factcheck.build(sop_header.scoring_text(text))
    return {
        "total_claims": worklist.total_claims,
        "uncited_claims": worklist.uncited_claims,
        "high_risk_count": len(worklist.high_risk),
        "items": [asdict(i) for i in worklist.items[:100]],
    }
