"""OpenAI-compatible LLM client.

The OpenAI Chat Completions API is a de-facto standard: OpenAI itself, plus Ollama
(local), OpenRouter, Groq, Together, DeepSeek, Mistral, and xAI all speak it. One
client, parameterized by base_url + key + model, therefore covers the famous closed
model (GPT) and open-source access to Llama / Mistral / Qwen / DeepSeek / Gemma / etc.

The `openai` package is imported lazily, so it's only required when such a provider is
actually selected.
"""
from __future__ import annotations

from typing import Optional

from app.llm.client import LLMClient, LLMResponse


class OpenAICompatibleClient(LLMClient):
    def __init__(
        self,
        *,
        model: str,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        json_mode: bool = True,
    ):
        self._model = model
        self._base_url = base_url
        self._api_key = api_key or "not-needed"  # e.g. local Ollama ignores the key
        self._json_mode = json_mode
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI  # lazy

            self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    async def complete(
        self, *, system: str, prompt: str, max_tokens: int = 16000,
        temperature: float = 0.0,
    ) -> LLMResponse:
        client = self._get_client()
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        # temperature 0 (+ a fixed seed where the provider honours it) makes scoring
        # reproducible: identical content yields identical model output.
        base = dict(
            model=self._model, messages=messages, max_tokens=max_tokens,
            temperature=temperature, seed=7,
        )

        # Try JSON mode first (GPT/Claude honor it). Some OpenRouter models don't
        # support response_format and 400 — retry once without it; the prompt still
        # asks for JSON and the evaluator repairs anything malformed.
        try:
            kwargs = dict(base)
            if self._json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            resp = await client.chat.completions.create(**kwargs)
        except Exception:
            if not self._json_mode:
                raise
            resp = await client.chat.completions.create(**base)

        choice = resp.choices[0]
        text = choice.message.content or ""
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=text,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )
