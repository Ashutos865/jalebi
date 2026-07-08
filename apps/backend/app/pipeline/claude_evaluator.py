"""Back-compat shim.

The Claude-specific evaluator was generalized into the provider-agnostic
`LLMEvaluator` (see llm_evaluator.py). `ClaudeEvaluator` remains as a convenience
that binds it to the Anthropic client.
"""
from __future__ import annotations

from typing import Optional

from app.llm.client import AnthropicClient, LLMClient
from app.pipeline.llm_evaluator import LLMEvaluator


class ClaudeEvaluator(LLMEvaluator):
    def __init__(self, client: Optional[LLMClient] = None, max_attempts: int = 2):
        super().__init__(
            client=client or AnthropicClient(),
            provider="anthropic",
            model="claude-opus-4-8",
            max_attempts=max_attempts,
        )
