"""Embeddings.

Default is a dependency-free hashing embedder — a hashed bag-of-words projected into
a fixed-dimension L2-normalized vector. It is deterministic, needs no model download,
and gives usable lexical similarity for retrieval out of the box. Swap to a real
embedding model (OpenAI, sentence-transformers) via JALEBI_EMBEDDING for production
semantic recall — the interface is the same.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import List

from app.config import settings

DIM = 256
_WORD = re.compile(r"[a-z0-9']+")


def _hash_embed(text: str) -> List[float]:
    vec = [0.0] * DIM
    for tok in _WORD.findall(text.lower()):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        idx = h % DIM
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _openai_embed(texts: List[str]) -> List[List[float]]:  # pragma: no cover (needs key)
    from openai import OpenAI

    client = OpenAI(api_key=settings.anthropic_api_key or None)  # OPENAI_API_KEY via env
    model = "text-embedding-3-small"
    resp = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in resp.data]


def embed(texts: List[str]) -> List[List[float]]:
    if settings.embedding_backend == "openai":
        try:
            return _openai_embed(texts)
        except Exception:
            pass  # fall back to hashing if the provider is unavailable
    return [_hash_embed(t) for t in texts]


def cosine(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))  # both are L2-normalized
