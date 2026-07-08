"""MultiAgentEvaluator (P5).

Instead of one monolithic prompt, this decomposes the rubric into focused reviewer
"agents" (grouped dimensions), runs them concurrently, then a deterministic judge
aggregates their category scores into the final scorecard. This is the LangGraph-style
pipeline shape — more consistent and transparent than a single prompt, and each agent
can be tuned independently.

Enable with JALEBI_PIPELINE=multi. Same `LLMClient`, same wire contract.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Awaitable, Callable, List, Optional

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from app.llm.client import LLMClient
from app.pipeline.base import Evaluator
from app.pipeline import aggregate as agg
from app.pipeline.prompt import EDITORIAL_DNA
from app.pipeline.text_features import analyze
from app.rubrics import Dimension, Rubric, get_rubric
from app.schemas.evaluation import (
    CategoryScore,
    EvaluationMeta,
    EvaluationRequest,
    EvaluationResult,
    Issue,
)
from app.util import elapsed_ms, now

Retriever = Callable[[str, str], Awaitable[List[str]]]
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
_GROUP_SIZE = 3


class _AgentCategory(BaseModel):
    name: str
    key: str
    score: int = Field(..., ge=0, le=100)
    summary: str = ""
    issues: List[Issue] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


_CATEGORIES = TypeAdapter(List[_AgentCategory])


def _strip(text: str) -> str:
    text = text.strip()
    return _FENCE.sub("", text).strip() if text.startswith("```") else text


def _chunk(items, n):
    return [items[i:i + n] for i in range(0, len(items), n)]


class MultiAgentEvaluator(Evaluator):
    def __init__(
        self,
        *,
        client: LLMClient,
        provider: str = "llm",
        model: str = "",
        retriever: Optional[Retriever] = None,
    ):
        self._client = client
        self.name = provider
        self._model = model
        self._retriever = retriever

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        started = now()
        rubric = get_rubric(request.content_type)
        features = analyze(request.text)

        knowledge: List[str] = []
        if self._retriever is not None:
            try:
                knowledge = await self._retriever(request.text, request.content_type.value)
            except Exception:
                knowledge = []

        groups = _chunk(rubric.dimensions, _GROUP_SIZE)
        results = await asyncio.gather(
            *(self._review_group(rubric, g, request, knowledge) for g in groups),
            return_exceptions=True,
        )

        categories: List[CategoryScore] = []
        for group_cats in results:
            if isinstance(group_cats, Exception):
                continue  # a failed agent drops its group rather than the whole eval
            categories.extend(group_cats)

        # Backfill any dimension whose agent failed, so the scorecard is complete.
        have = {c.key for c in categories}
        for dim in rubric.dimensions:
            if dim.key not in have:
                categories.append(CategoryScore(
                    name=dim.name, key=dim.key, score=70, weight=dim.weight,
                    summary="Reviewer unavailable; neutral placeholder score.",
                ))

        a = agg.aggregate(categories)
        summary = agg.summarize(
            a["overall"], a["readiness"], len(a["critical_issues"]), rubric.label
        )
        return EvaluationResult(
            overall_score=a["overall"],
            publication_ready=a["publication_ready"],
            publication_readiness=a["readiness"],
            content_type=request.content_type,
            summary=summary,
            categories=categories,
            critical_issues=a["critical_issues"],
            strengths=a["strengths"],
            next_steps=a["next_steps"],
            meta=EvaluationMeta(
                evaluator=f"{self.name}+multi",
                model=self._model,
                content_type=request.content_type,
                word_count=features.word_count,
                duration_ms=elapsed_ms(started),
                knowledge_used=len(knowledge),
            ),
        )

    async def _review_group(
        self, rubric: Rubric, dims: List[Dimension],
        request: EvaluationRequest, knowledge: List[str],
    ) -> List[CategoryScore]:
        dim_lines = "\n".join(f"- {d.key} ({d.name}): {d.description}" for d in dims)
        kb = ("\nApply this TIES knowledge:\n" + "\n".join(knowledge)) if knowledge else ""
        system = (
            f"{EDITORIAL_DNA}\n{kb}\n\n"
            f"You are reviewing ONLY these dimensions of a {rubric.label}:\n{dim_lines}\n\n"
            "Return ONLY a JSON array (no prose, no fences). One object per dimension:\n"
            '[{"name":"...","key":"<exact key>","score":<0-100>,"summary":"...",'
            '"issues":[{"problem":"...","explanation":"...","impact":"...",'
            '"suggestion":"...","priority":"critical|high|medium|low",'
            '"example":null,"quote":null}],"recommendations":["..."]}]'
        )
        user = (
            f"TITLE: {request.title or 'Untitled'}\n\n"
            f"--- DOCUMENT ---\n{request.text}\n--- END ---\n\n"
            "Review the listed dimensions and return the JSON array."
        )
        resp = await self._client.complete(system=system, prompt=user)
        try:
            parsed = _CATEGORIES.validate_json(_strip(resp.text))
        except (ValidationError, json.JSONDecodeError, ValueError):
            return []
        out = []
        for c in parsed:
            out.append(CategoryScore(
                name=c.name, key=c.key, score=c.score,
                weight=rubric.weight_of(c.key), summary=c.summary,
                issues=c.issues, recommendations=c.recommendations,
            ))
        return out
