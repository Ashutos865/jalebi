"""Provider-abstracted LLM client.

Keeps the model provider swappable and keeps API keys on the backend only. The
Anthropic implementation follows the current SDK guidance: adaptive thinking, the
`effort` output control, and prompt caching on the (stable) system prompt. The
`anthropic` package is imported lazily so mock mode has no dependency on it.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Optional

from app.config import settings


@dataclass
class LLMResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0


class LLMClient(abc.ABC):
    @abc.abstractmethod
    async def complete(self, *, system: str, prompt: str, max_tokens: int = 16000) -> LLMResponse:
        """Return a completion. The provider handles thinking/effort/caching."""
        ...


class AnthropicClient(LLMClient):
    """Claude client using the official Anthropic async SDK."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._api_key = api_key or settings.anthropic_api_key
        self._model = model or settings.anthropic_model
        self._client = None  # lazily constructed

    def _get_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic  # lazy — only when evaluator=claude

            # AsyncAnthropic() also resolves ANTHROPIC_API_KEY / ant-login profiles
            # from the environment; pass an explicit key only when we have one.
            self._client = (
                AsyncAnthropic(api_key=self._api_key)
                if self._api_key
                else AsyncAnthropic()
            )
        return self._client

    async def complete(
        self, *, system: str, prompt: str, max_tokens: int = 16000
    ) -> LLMResponse:
        client = self._get_client()
        # The system prompt is stable per content type — cache it so repeat
        # evaluations of the same content type reuse the prefix.
        system_blocks = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ]
        message = await client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            output_config={"effort": settings.effort},
            system=system_blocks,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in message.content if b.type == "text")
        usage = message.usage
        return LLMResponse(
            text=text,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        )
