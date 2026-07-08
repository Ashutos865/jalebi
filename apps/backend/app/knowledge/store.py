"""Vector store — in-memory by default, Qdrant when configured.

The in-memory store keeps the whole app runnable with zero infra; it's rebuilt from
the `knowledge_docs` table on startup. Set `QDRANT_URL` to use Qdrant for persistence
and scale.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import List, Optional

from app.config import settings
from app.knowledge.embeddings import cosine


@dataclass
class Hit:
    text: str
    score: float
    payload: dict


class InMemoryStore:
    def __init__(self):
        self._items: List[dict] = []  # {id, vector, text, content_type, payload}
        self._lock = threading.Lock()

    def clear(self) -> None:
        with self._lock:
            self._items = []

    def upsert(self, *, id: str, vector: List[float], text: str,
               content_type: Optional[str], payload: dict) -> None:
        with self._lock:
            self._items = [i for i in self._items if i["id"] != id]
            self._items.append({
                "id": id, "vector": vector, "text": text,
                "content_type": content_type, "payload": payload,
            })

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            self._items = [i for i in self._items if not i["id"].startswith(prefix)]

    def search(self, vector: List[float], *, top_k: int,
               content_type: Optional[str] = None) -> List[Hit]:
        with self._lock:
            items = self._items
            candidates = [
                i for i in items
                if content_type is None or i["content_type"] in (None, content_type)
            ] or items
            scored = [(cosine(vector, i["vector"]), i) for i in candidates]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [Hit(text=i["text"], score=s, payload=i["payload"]) for s, i in scored[:top_k]]

    def count(self) -> int:
        return len(self._items)


class QdrantStore:  # pragma: no cover — requires a running Qdrant
    COLLECTION = "jalebi_knowledge"

    def __init__(self):
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as qm

        from app.knowledge.embeddings import DIM

        self._qm = qm
        self._client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
        existing = {c.name for c in self._client.get_collections().collections}
        if self.COLLECTION not in existing:
            self._client.create_collection(
                self.COLLECTION,
                vectors_config=qm.VectorParams(size=DIM, distance=qm.Distance.COSINE),
            )

    def clear(self) -> None:
        self._client.delete_collection(self.COLLECTION)

    def upsert(self, *, id, vector, text, content_type, payload):
        self._client.upsert(self.COLLECTION, points=[self._qm.PointStruct(
            id=abs(hash(id)) % (10 ** 18),
            vector=vector,
            payload={"text": text, "content_type": content_type, **payload, "_key": id},
        )])

    def delete_prefix(self, prefix: str) -> None:
        pass  # handled by full reindex

    def search(self, vector, *, top_k, content_type=None):
        flt = None
        if content_type:
            flt = self._qm.Filter(should=[
                self._qm.FieldCondition(key="content_type",
                                        match=self._qm.MatchValue(value=content_type)),
                self._qm.FieldCondition(key="content_type",
                                        match=self._qm.MatchValue(value=None)),
            ])
        res = self._client.search(self.COLLECTION, query_vector=vector, limit=top_k, query_filter=flt)
        return [Hit(text=p.payload.get("text", ""), score=p.score, payload=p.payload) for p in res]

    def count(self) -> int:
        return self._client.count(self.COLLECTION).count


_store = None


def get_store():
    global _store
    if _store is None:
        if settings.qdrant_url:
            try:
                _store = QdrantStore()
            except Exception:
                _store = InMemoryStore()
        else:
            _store = InMemoryStore()
    return _store
