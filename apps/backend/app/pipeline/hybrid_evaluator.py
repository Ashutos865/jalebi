"""HybridEvaluator — the TIES scoring pipeline.

Runs the deterministic rules engine (~70%), asks the model for constrained judgment
(~30%, temperature 0), and combines them under the Constitution's weights and hard
caps. An in-process cache keyed by content hash guarantees that re-evaluating the
same article returns an identical result — killing the score wobble.

When `client is None` (mock provider) it runs rules-only: still deterministic,
still rule-anchored, no model call.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from typing import Awaitable, Callable, List, Optional

from app.llm.client import LLMClient
from app.pipeline.base import Evaluator
from app.pipeline.text_features import analyze
from app.scoring import ai_prompt, rules, sop_compliance, sop_header
from app.scoring.engine import AIReport, combine
from app.schemas.evaluation import (
    EvaluationMeta, EvaluationRequest, EvaluationResult,
    SopCheckItem, SopComplianceReport,
)
from app.util import elapsed_ms, now

Retriever = Callable[[str, str], Awaitable[List[str]]]

# content-hash -> AIReport. Bounded; identical content reuses the same judgment.
_AI_CACHE: "OrderedDict[str, AIReport]" = OrderedDict()
_AI_CACHE_MAX = 256


def _content_key(text: str, content_type: str, model: str) -> str:
    norm = re.sub(r"\s+", " ", text.strip())
    return hashlib.sha256(f"{model}|{content_type}|{norm}".encode()).hexdigest()


def _sop_report(
    header: sop_header.SopHeader,
    body: str,
    content_type: str,
    word_min: Optional[int],
    word_max: Optional[int],
) -> SopComplianceReport:
    """Mechanical SOP compliance, reported beside the editorial score.

    Skipped entirely for documents with no SOP header: most content Jalebi sees
    is not a TIES assignment, and a wall of red checks on an ordinary draft is
    noise, not feedback.
    """
    if not header.present:
        return SopComplianceReport(checked=False)

    report = sop_compliance.evaluate(header, body, content_type, word_min, word_max)
    return SopComplianceReport(
        checked=True,
        compliant=report.compliant,
        checks=[
            SopCheckItem(
                name=c.name, passed=c.passed, detail=c.detail, severity=c.severity
            )
            for c in report.checks
        ],
        header_present=True,
        header_fields=dict(header.fields),
        missing_fields=list(header.missing),
        word_count=report.word_count,
        word_min=report.word_min,
        word_max=report.word_max,
        reference_urls=list(header.reference_urls),
    )


class HybridEvaluator(Evaluator):
    def __init__(
        self,
        *,
        client: Optional[LLMClient] = None,
        provider: str = "hybrid",
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
        ct = request.content_type.value

        # TIES SOP: the pre-drafting header block and the references list are
        # metadata, not prose. Grading them inflates the word count (against a
        # strict 300-350 window) and skews sourcing/headline scores, so the
        # article body is isolated first. Documents with no header are unchanged.
        header = sop_header.parse(request.text)
        body = header.body or request.text

        features = analyze(body)

        knowledge: List[str] = []
        if self._retriever is not None:
            try:
                knowledge = await self._retriever(body, ct)
            except Exception:
                knowledge = []

        # Prefer the SOP HEADING over the Google Doc filename when present.
        title = header.get("heading") or request.title

        rule_report = rules.analyze(body, title, ct)
        ai_report = await self._judge(request, knowledge, body=body, title=title)
        composed = combine(rule_report, ai_report, ct)
        sop = _sop_report(header, body, ct, request.word_min, request.word_max)

        return EvaluationResult(
            overall_score=composed.overall,
            publication_ready=composed.publication_ready,
            publication_readiness=composed.readiness,
            content_type=request.content_type,
            summary=composed.summary,
            categories=composed.categories,
            critical_issues=composed.critical_issues,
            strengths=composed.strengths,
            next_steps=composed.next_steps,
            sop=sop,
            meta=EvaluationMeta(
                evaluator=self.name, model=self._model,
                content_type=request.content_type, word_count=features.word_count,
                duration_ms=elapsed_ms(started), knowledge_used=len(knowledge),
            ),
        )

    async def _judge(
        self,
        request: EvaluationRequest,
        knowledge: List[str],
        body: Optional[str] = None,
        title: Optional[str] = None,
    ) -> AIReport:
        """Constrained AI judgment, cached by content hash for reproducibility.

        `body`/`title` are the SOP-stripped article and heading; the model judges
        the writing, not the metadata block.
        """
        if self._client is None:
            return AIReport()  # rules-only; engine falls back to rule scores

        text = body if body is not None else request.text
        heading = title if title is not None else request.title

        key = _content_key(text, request.content_type.value, self._model)
        if key in _AI_CACHE:
            _AI_CACHE.move_to_end(key)
            return _AI_CACHE[key]

        system = ai_prompt.build_system(request.content_type.value, knowledge)
        user = ai_prompt.build_user(heading, text)
        report = await self._call_with_repair(system, user)

        _AI_CACHE[key] = report
        _AI_CACHE.move_to_end(key)
        if len(_AI_CACHE) > _AI_CACHE_MAX:
            _AI_CACHE.popitem(last=False)
        return report

    async def _call_with_repair(self, system: str, user: str) -> AIReport:
        prompt = user
        last = ""
        for _ in range(self._max_attempts):
            resp = await self._client.complete(
                system=system, prompt=prompt, temperature=0.0
            )
            try:
                return ai_prompt.parse(resp.text)
            except (json.JSONDecodeError, ValueError) as e:
                last = str(e)
                prompt = (
                    f"{user}\n\nYour previous reply was not valid JSON ({last}). "
                    "Return ONLY the corrected JSON object."
                )
        # Judgment failed after retries — degrade to rules-only rather than error out.
        return AIReport(summary="(AI judgment unavailable; scored on deterministic rules.)")
