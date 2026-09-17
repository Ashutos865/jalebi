"""Google Gemini LLM client (google-genai SDK, imported lazily)."""
from __future__ import annotations

from typing import Optional

from app.llm.client import LLMClient, LLMResponse


class GeminiClient(LLMClient):
    def __init__(self, *, model: str, api_key: Optional[str] = None):
        self._model = model
        self._api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai  # lazy

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def complete(
        self, *, system: str, prompt: str, max_tokens: int = 16000,
        temperature: float = 0.0,
    ) -> LLMResponse:
        client = self._get_client()
        resp = await client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config={
                "system_instruction": system,
                "response_mime_type": "application/json",
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        text = getattr(resp, "text", "") or ""
        usage = getattr(resp, "usage_metadata", None)
        return LLMResponse(
            text=text,
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        )
