"""Evaluator interface.

`Evaluator` is the seam between the API and whatever produces the scorecard, so
the API and UI never learn which implementation ran. Today that is
`HybridEvaluator` (deterministic rules + constrained AI judgment); the mock
provider is the same class with no LLM client.
"""
from __future__ import annotations

import abc

from app.schemas.evaluation import EvaluationRequest, EvaluationResult


class Evaluator(abc.ABC):
    """Produces a full `EvaluationResult` for a request."""

    name: str = "base"

    @abc.abstractmethod
    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        ...
