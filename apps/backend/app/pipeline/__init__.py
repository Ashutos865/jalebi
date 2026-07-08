"""Pipeline package — evaluator selection.

`get_evaluator(provider=None)` returns the configured `Evaluator`. The active provider
comes from `JALEBI_PROVIDER`; a request may override it to any allowed provider. RAG
retrieval is injected for non-mock providers when the knowledge base is enabled.
"""
from __future__ import annotations

from typing import Optional

from app.config import settings
from app.llm import registry
from app.pipeline.base import Evaluator


def _retriever():
    if not settings.rag_enabled:
        return None
    try:
        from app.knowledge.service import retrieve_passages

        return retrieve_passages
    except Exception:
        return None


def get_evaluator(provider: Optional[str] = None) -> Evaluator:
    provider_id = provider or settings.provider
    retriever = None if provider_id == "mock" else _retriever()
    return registry.build_evaluator(provider_id, retriever=retriever)
