"""GET /api/providers — which AI backends the writer may pick.

Only providers the backend has configured (key present, or keyless like Ollama) and
that pass the allow-list are returned. Keys never leave the backend.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.llm import registry
from app.schemas.evaluation import ProviderOption, ProvidersResponse

router = APIRouter(tags=["providers"])


# response_model so the shape the sidebar depends on is enforced and documented,
# rather than being asserted only by the TypeScript interface.
@router.get("/providers", response_model=ProvidersResponse)
async def providers() -> ProvidersResponse:
    allowed = {p.id for p in registry.allowed_providers()}
    return ProvidersResponse(
        active=settings.provider,
        providers=[
            ProviderOption(
                id=p.id,
                label=p.label,
                open_source=p.open_source,
                model=p.model(),
                available=p.id in allowed,
                note=p.note,
            )
            for p in registry.PROVIDERS.values()
        ],
    )
