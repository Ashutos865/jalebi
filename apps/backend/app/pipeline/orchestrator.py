"""Orchestrator + MockEvaluator.

Runs the editorial pipeline for one document:
  1. classify   — resolve the rubric for the content type (writer-selected in v1)
  2. review      — run each dimension's reviewer against the text features
  3. judge       — weight the scores, decide publication readiness, assemble the report

`MockEvaluator` wires the content-aware reviewers into this pipeline. Scoring policy
(weighting, readiness, next-steps) is shared with the multi-agent pipeline via
`aggregate`.
"""
from __future__ import annotations

import hashlib
import random
from typing import List

from app.pipeline import aggregate as agg
from app.pipeline.base import Evaluator
from app.pipeline.mock_reviewer import REVIEWERS
from app.pipeline import text_features
from app.rubrics import get_rubric
from app.schemas.evaluation import (
    CategoryScore,
    EvaluationMeta,
    EvaluationRequest,
    EvaluationResult,
)
from app.util import elapsed_ms, now


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


class MockEvaluator(Evaluator):
    """Deterministic, content-aware stand-in for a real model."""

    name = "mock"

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        started = now()

        rubric = get_rubric(request.content_type)
        features = text_features.analyze(request.text)
        from app.pipeline.base import PipelineContext

        ctx = PipelineContext(request=request, rubric=rubric, features=features)
        rng = random.Random(_seed(request.text))

        categories: List[CategoryScore] = []
        for dim in rubric.dimensions:
            score, issues, recs, summary = REVIEWERS[dim.key](ctx, rng)
            categories.append(CategoryScore(
                name=dim.name, key=dim.key, score=score, weight=dim.weight,
                summary=summary, issues=issues, recommendations=recs,
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
                evaluator=self.name,
                content_type=request.content_type,
                word_count=features.word_count,
                duration_ms=elapsed_ms(started),
            ),
        )
