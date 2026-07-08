"""LLMEvaluator — provider-agnostic editorial reviewer.

Given any `LLMClient` it prompts the model as a Senior Managing Editor using the
content-type rubric and TIES' Editorial DNA, validates the JSON against the scorecard
contract, and maps it to the wire type — injecting rubric weights and metadata so
those stay authoritative regardless of which model ran.

The same class serves Claude, GPT, Gemini, Grok, or any open-source model behind an
`LLMClient`. An optional `retriever` prepends knowledge-base passages (RAG, P4).
"""
from __future__ import annotations

import json
import re
from typing import Awaitable, Callable, List, Optional

from pydantic import BaseModel, Field, ValidationError

from app.llm.client import LLMClient
from app.pipeline import prompt as prompt_builder
from app.pipeline.base import Evaluator
from app.pipeline.text_features import analyze
from app.rubrics import get_rubric
from app.schemas.evaluation import (
    CategoryScore,
    EvaluationMeta,
    EvaluationRequest,
    EvaluationResult,
    Issue,
    PublicationReadiness,
)
from app.util import elapsed_ms, now

# (text, content_type) -> list of knowledge passages
Retriever = Callable[[str, str], Awaitable[List[str]]]

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class _LLMCategory(BaseModel):
    name: str
    key: str
    score: int = Field(..., ge=0, le=100)
    summary: str = ""
    issues: List[Issue] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class _LLMResult(BaseModel):
    overall_score: int = Field(..., ge=0, le=100)
    publication_ready: bool
    publication_readiness: PublicationReadiness
    summary: str
    categories: List[_LLMCategory] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    # `critical_issues` is intentionally NOT modeled — we derive it on the backend
    # from the category issues, so weaker models can't break validation by returning
    # a simplified shape here. Any critical_issues the model emits is ignored.


def strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = _FENCE.sub("", text)
    return text.strip()


class LLMEvaluator(Evaluator):
    def __init__(
        self,
        *,
        client: LLMClient,
        provider: str = "llm",
        model: str = "",
        retriever: Optional[Retriever] = None,
        max_attempts: int = 2,
    ):
        self._client = client
        self.name = provider
        self._model = model
        self._retriever = retriever
        self._max_attempts = max_attempts

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        started = now()
        rubric = get_rubric(request.content_type)
        features = analyze(request.text)

        knowledge: List[str] = []
        if self._retriever is not None:
            try:
                knowledge = await self._retriever(request.text, request.content_type.value)
            except Exception:  # RAG is best-effort; never fail an evaluation over it
                knowledge = []

        system = prompt_builder.build_system(rubric, knowledge=knowledge)
        user = prompt_builder.build_user(
            title=request.title, text=request.text, features=features
        )
        llm_result = await self._call_with_repair(system, user)

        categories = [
            CategoryScore(
                name=c.name, key=c.key, score=c.score,
                weight=rubric.weight_of(c.key), summary=c.summary,
                issues=c.issues, recommendations=c.recommendations,
            )
            for c in llm_result.categories
        ]
        # Derive critical issues from the category issues (high/critical, most-severe
        # first) — robust regardless of what the model returns for critical_issues.
        from app.pipeline.aggregate import PRIORITY_RANK
        from app.schemas.evaluation import Priority

        all_issues = [i for c in categories for i in c.issues]
        critical_issues = sorted(
            [i for i in all_issues if i.priority in (Priority.critical, Priority.high)],
            key=lambda i: PRIORITY_RANK[i.priority],
        )
        return EvaluationResult(
            overall_score=llm_result.overall_score,
            publication_ready=llm_result.publication_ready,
            publication_readiness=llm_result.publication_readiness,
            content_type=request.content_type,
            summary=llm_result.summary,
            categories=categories,
            critical_issues=critical_issues,
            strengths=llm_result.strengths,
            next_steps=llm_result.next_steps,
            meta=EvaluationMeta(
                evaluator=self.name,
                model=self._model,
                content_type=request.content_type,
                word_count=features.word_count,
                duration_ms=elapsed_ms(started),
                knowledge_used=len(knowledge),
            ),
        )

    async def _call_with_repair(self, system: str, user: str) -> _LLMResult:
        last_error = ""
        prompt = user
        for _ in range(self._max_attempts):
            response = await self._client.complete(system=system, prompt=prompt)
            raw = strip_fences(response.text)
            try:
                return _LLMResult.model_validate_json(raw)
            except (ValidationError, json.JSONDecodeError, ValueError) as e:
                last_error = str(e)
                prompt = (
                    f"{user}\n\nYour previous response was not valid per the schema:\n"
                    f"{last_error}\n\nReturn ONLY the corrected JSON object."
                )
        raise ValueError(
            f"{self.name} did not return valid evaluation JSON after "
            f"{self._max_attempts} attempts: {last_error}"
        )
