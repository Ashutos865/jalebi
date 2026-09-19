"""Reindexing must not blank the knowledge base while the service is live.

An admin can trigger reindex_all from the API. It cleared the store first, so
for the whole length of the rebuild every concurrent evaluation retrieved
nothing and scored without the handbook -- silently, while RAG reported
success. Same failure mode as the RAG cache bug fixed earlier.
"""
from __future__ import annotations

import asyncio

from app.knowledge import service
from app.knowledge.store import get_store


class _Doc:
    """Stand-in for a KnowledgeDoc row."""

    def __init__(self, doc_id: int, content: str):
        self.id = doc_id
        self.content = content
        self.content_type = None
        self.kind = "handbook"
        self.title = f"doc-{doc_id}"


class _Session:
    """Just enough AsyncSession to satisfy reindex_all's single select."""

    def __init__(self, docs):
        self._docs = docs

    async def execute(self, *args, **kwargs):
        docs = self._docs

        class _Result:
            def scalars(self):
                class _Scalars:
                    def all(self):
                        return docs

                return _Scalars()

        return _Result()


def _docs(*ids):
    return [_Doc(i, f"handbook passage about attribution {i} " * 60) for i in ids]


def test_a_concurrent_reader_never_sees_an_empty_store(monkeypatch):
    """Sampling from another thread cannot catch a sub-millisecond rebuild, so
    the read is placed at a known point inside it -- between documents, exactly
    where a concurrent evaluation would land."""
    docs = _docs(1, 2, 3, 4, 5)
    asyncio.run(service.reindex_all(_Session(docs)))
    assert get_store().count() > 0, "fixture failed to index"

    seen = []
    real_index_doc = service.index_doc

    def spy(doc):
        seen.append(get_store().count())
        return real_index_doc(doc)

    monkeypatch.setattr(service, "index_doc", spy)
    asyncio.run(service.reindex_all(_Session(docs)))

    # Pre-fix this read [0, 4, 8, 12, 16]: the first evaluation to arrive got
    # nothing at all, and the rest got a partial index.
    assert min(seen) > 0, f"a reader saw an empty knowledge base: {seen}"


def test_the_index_is_complete_after_a_reindex():
    docs = _docs(1, 2, 3)
    asyncio.run(service.reindex_all(_Session(docs)))
    first = get_store().count()

    asyncio.run(service.reindex_all(_Session(docs)))
    assert get_store().count() == first, "reindexing changed the chunk count"


def test_documents_deleted_from_the_db_are_pruned():
    """The up-front clear() was what removed deleted documents. Rebuilding in
    place has to prune them explicitly instead."""
    docs = _docs(1, 2, 3)
    asyncio.run(service.reindex_all(_Session(docs)))
    before = get_store().count()

    asyncio.run(service.reindex_all(_Session(docs[:2])))
    assert get_store().count() < before
    assert not any(k.startswith("kdoc:3:") for k in get_store().ids())
