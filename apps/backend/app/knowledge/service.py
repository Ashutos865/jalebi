"""Knowledge-base service: ingest, index, retrieve, reindex.

`retrieve_passages` is the RAG hook the evaluators call before scoring — it returns
the most relevant handbook / exemplar / founder-note passages for the document, which
the prompt-builder folds into the system prompt.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import KnowledgeDoc
from app.knowledge.embeddings import embed
from app.knowledge.store import get_store


def _chunk(text: str, size: int = 700, overlap: int = 120) -> List[str]:
    text = " ".join(text.split())
    if len(text) <= size:
        return [text] if text else []
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks


def index_doc(doc: KnowledgeDoc) -> int:
    """Embed a knowledge doc's chunks into the vector store. Returns chunk count."""
    store = get_store()
    store.delete_prefix(f"kdoc:{doc.id}:")
    chunks = _chunk(doc.content)
    if not chunks:
        return 0
    vectors = embed(chunks)
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        store.upsert(
            id=f"kdoc:{doc.id}:{i}",
            vector=vec,
            text=chunk,
            content_type=doc.content_type,
            payload={"doc_id": doc.id, "kind": doc.kind, "title": doc.title},
        )
    return len(chunks)


async def create_knowledge_doc(
    session: AsyncSession, *, kind: str, title: str, content: str,
    content_type: Optional[str] = None, created_by: Optional[int] = None,
) -> KnowledgeDoc:
    doc = KnowledgeDoc(
        kind=kind, title=title, content=content,
        content_type=content_type, created_by=created_by,
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    index_doc(doc)
    return doc


async def reindex_all(session: AsyncSession) -> int:
    """Rebuild the vector store from the DB (called on startup, and by admins).

    Re-indexed in place rather than cleared first. `clear()` emptied the store
    for the whole length of the rebuild, and an admin can trigger this from the
    API while the service is live -- so every evaluation landing in that window
    silently retrieved nothing and scored without the handbook, exactly the
    failure mode where RAG reports success while doing nothing.

    `index_doc` already replaces each document's own chunks, so rebuilding first
    and pruning afterwards leaves the store continuously serving. The prune
    removes chunks for documents that have since been deleted from the DB.
    """
    docs = (await session.execute(select(KnowledgeDoc))).scalars().all()
    total = 0
    live_ids = set()
    for doc in docs:
        total += index_doc(doc)
        live_ids.add(doc.id)

    store = get_store()
    for stale_id in _indexed_doc_ids(store) - live_ids:
        store.delete_prefix(f"kdoc:{stale_id}:")
    return total


def _indexed_doc_ids(store) -> set:
    """Document ids currently present in the store, from the chunk keys.

    Keys are "kdoc:<doc id>:<chunk>". A store that cannot enumerate its keys
    (Qdrant) returns nothing, so no pruning happens there; its chunks are still
    replaced per document by index_doc.
    """
    ids = set()
    for key in getattr(store, "ids", lambda: [])():
        parts = key.split(":")
        if len(parts) >= 3 and parts[0] == "kdoc":
            try:
                ids.add(int(parts[1]))
            except ValueError:
                continue
    return ids


async def retrieve_passages(text: str, content_type: str) -> List[str]:
    """RAG retriever used by the evaluators. Best-effort; returns [] if empty."""
    if not settings.rag_enabled or get_store().count() == 0:
        return []
    query_vec = embed([text[:2000]])[0]
    hits = get_store().search(query_vec, top_k=settings.rag_top_k, content_type=content_type)
    # Only keep reasonably-relevant passages.
    return [h.text for h in hits if h.score > 0.05]
