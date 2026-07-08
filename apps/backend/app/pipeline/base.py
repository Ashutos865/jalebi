"""Evaluator interface + pipeline context.

`Evaluator` is the seam between the API and whatever produces the scorecard. Today
that's `MockEvaluator`; in P2 `ClaudeEvaluator` implements the same interface and the
API/UI never learn which ran. The editorial review is a **pipeline** — classify →
review each dimension → judge readiness — so the structure survives the swap.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass

from app.rubrics import Rubric
from app.schemas.evaluation import EvaluationRequest, EvaluationResult
from app.pipeline.text_features import TextFeatures


@dataclass
class PipelineContext:
    """Everything a reviewer stage needs, assembled once per evaluation."""

    request: EvaluationRequest
    rubric: Rubric
    features: TextFeatures

    @property
    def text(self) -> str:
        return self.request.text


class Evaluator(abc.ABC):
    """Produces a full `EvaluationResult` for a request."""

    name: str = "base"

    @abc.abstractmethod
    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        ...
