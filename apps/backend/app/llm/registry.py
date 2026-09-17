"""Provider registry — the catalogue of AI backends Jalebi can use.

Each provider is metadata: how to build its client, which env var holds the key, and
a default model. Availability is derived from whether the key is configured, so the
sidebar only offers providers the backend can actually reach. Keys never leave the
backend.

Add a provider by adding one `ProviderSpec` — no other code changes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from app.config import settings
from app.llm.client import LLMClient


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    kind: str                      # mock | anthropic | openai_compat | gemini
    key_env: str = ""              # env var holding the API key ("" = no key needed)
    model_env: str = ""            # env var overriding the model
    default_model: str = ""        # used when model_env is unset
    base_url: str = ""             # for openai_compat providers
    json_mode: bool = True
    open_source: bool = False      # serves open-weight models
    note: str = ""

    @property
    def needs_key(self) -> bool:
        return bool(self.key_env)

    def api_key(self) -> str:
        return os.getenv(self.key_env, "") if self.key_env else ""

    def model(self) -> str:
        return (os.getenv(self.model_env) if self.model_env else "") or self.default_model

    def is_configured(self) -> bool:
        if self.kind == "mock":
            return True
        if self.needs_key and not self.api_key():
            return False
        return True  # keyless providers (e.g. local Ollama) are always "configured"


# Closed models get confident defaults only where the ID is stable in this skill
# (Anthropic). For others we require an explicit model env so we never ship a stale
# model id — the registry raises a clear error if it's missing.
PROVIDERS: Dict[str, ProviderSpec] = {
    "mock": ProviderSpec("mock", "Jalebi Mock", "mock",
                         note="Deterministic, content-aware. No API key needed."),
    "anthropic": ProviderSpec("anthropic", "Claude (Anthropic)", "anthropic",
                              key_env="ANTHROPIC_API_KEY", model_env="JALEBI_MODEL",
                              default_model="claude-opus-4-8"),
    "openai": ProviderSpec("openai", "GPT (OpenAI)", "openai_compat",
                           key_env="OPENAI_API_KEY", model_env="OPENAI_MODEL"),
    "gemini": ProviderSpec("gemini", "Gemini (Google)", "gemini",
                           key_env="GEMINI_API_KEY", model_env="GEMINI_MODEL"),
    "xai": ProviderSpec("xai", "Grok (xAI)", "openai_compat",
                        key_env="XAI_API_KEY", model_env="XAI_MODEL",
                        base_url="https://api.x.ai/v1"),
    "ollama": ProviderSpec("ollama", "Ollama (local, open source)", "openai_compat",
                           model_env="OLLAMA_MODEL", default_model="llama3.1",
                           base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                           json_mode=False, open_source=True,
                           note="Runs Llama/Mistral/Qwen/Gemma/DeepSeek locally."),
    "openrouter": ProviderSpec("openrouter", "OpenRouter (open + closed)", "openai_compat",
                               key_env="OPENROUTER_API_KEY", model_env="OPENROUTER_MODEL",
                               base_url="https://openrouter.ai/api/v1", open_source=True,
                               note="Gateway to many open and closed models."),
    "groq": ProviderSpec("groq", "Groq (fast open source)", "openai_compat",
                         key_env="GROQ_API_KEY", model_env="GROQ_MODEL",
                         base_url="https://api.groq.com/openai/v1", open_source=True),
    "together": ProviderSpec("together", "Together AI (open source)", "openai_compat",
                             key_env="TOGETHER_API_KEY", model_env="TOGETHER_MODEL",
                             base_url="https://api.together.xyz/v1", open_source=True),
    "deepseek": ProviderSpec("deepseek", "DeepSeek", "openai_compat",
                             key_env="DEEPSEEK_API_KEY", model_env="DEEPSEEK_MODEL",
                             default_model="deepseek-chat",
                             base_url="https://api.deepseek.com/v1", open_source=True),
    "mistral": ProviderSpec("mistral", "Mistral", "openai_compat",
                            key_env="MISTRAL_API_KEY", model_env="MISTRAL_MODEL",
                            base_url="https://api.mistral.ai/v1", open_source=True),
}


def get_spec(provider_id: str) -> ProviderSpec:
    if provider_id not in PROVIDERS:
        raise ValueError(f"Unknown provider {provider_id!r}. Known: {list(PROVIDERS)}")
    return PROVIDERS[provider_id]


def configured_providers() -> List[ProviderSpec]:
    return [p for p in PROVIDERS.values() if p.is_configured()]


def allowed_providers() -> List[ProviderSpec]:
    """Providers a request may select: configured ∩ (allow-list if set)."""
    allow = set(settings.allowed_providers)
    out = []
    for p in configured_providers():
        if allow and p.id not in allow:
            continue
        out.append(p)
    return out


def _build_client(spec: ProviderSpec) -> LLMClient:
    if spec.kind == "anthropic":
        from app.llm.client import AnthropicClient

        return AnthropicClient(api_key=spec.api_key() or None, model=spec.model())
    if spec.kind == "openai_compat":
        model = spec.model()
        if not model:
            raise ValueError(
                f"Provider {spec.id!r} needs a model. Set {spec.model_env} "
                f"(e.g. {spec.model_env}=<model-id>)."
            )
        from app.llm.openai_client import OpenAICompatibleClient

        return OpenAICompatibleClient(
            model=model,
            base_url=spec.base_url or None,
            api_key=spec.api_key() or None,
            json_mode=spec.json_mode,
        )
    if spec.kind == "gemini":
        model = spec.model()
        if not model:
            raise ValueError(
                f"Provider 'gemini' needs a model. Set {spec.model_env} "
                f"(e.g. {spec.model_env}=<model-id>)."
            )
        from app.llm.gemini_client import GeminiClient

        return GeminiClient(model=model, api_key=spec.api_key() or None)
    raise ValueError(f"No client builder for kind {spec.kind!r}")


def build_evaluator(provider_id: str, retriever=None):
    """Return an Evaluator for the given provider id (optional RAG retriever).

    All providers now run through the deterministic TIES HybridEvaluator (rules +
    constrained AI judgment). Mock runs rules-only (client=None): still fully
    deterministic and rule-anchored, no model call.
    """
    spec = get_spec(provider_id)
    from app.pipeline.hybrid_evaluator import HybridEvaluator

    client = None if spec.kind == "mock" else _build_client(spec)
    return HybridEvaluator(
        client=client,
        provider=spec.id,
        model=spec.model() if spec.kind != "mock" else "",
        retriever=retriever,
    )
