"""GET /api/providers — which AI backends the writer may pick.

Only providers the backend has configured (key present, or keyless like Ollama) and
that pass the allow-list are returned. Keys never leave the backend.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.llm import registry

router = APIRouter(tags=["providers"])


@router.get("/providers")
async def providers() -> dict:
    allowed = {p.id for p in registry.allowed_providers()}
    items = [
        {
            "id": p.id,
            "label": p.label,
            "open_source": p.open_source,
            "model": p.model(),
            "available": p.id in allowed,
            "note": p.note,
        }
        for p in registry.PROVIDERS.values()
    ]
    return {"active": settings.provider, "providers": items}
