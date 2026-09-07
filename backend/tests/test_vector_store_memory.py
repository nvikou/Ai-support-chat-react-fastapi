"""Unit tests for the VectorStore protocol and in-memory backend."""

from __future__ import annotations

from app.services.vector_store import InMemoryVectorStore
from app.services.vector_store import VectorStore


def test_inmemory_is_vector_store() -> None:
    store: VectorStore = InMemoryVectorStore()
    assert store.health().backend == "memory"
    assert store.health().ready is True


def test_inmemory_add_and_search() -> None:
    store = InMemoryVectorStore()
    added = store.add_documents(
        [
            {
                "content": "refund policy allows 30 days",
                "metadata": {"source": "faq"},
            },
            {
                "content": "shipping takes five business days",
                "metadata": {"source": "faq"},
            },
        ]
    )
    assert added == 2
    assert store.health().document_count == 2

    hits = store.search("refund policy", k=1)
    assert len(hits) == 1
    assert "refund" in hits[0].content
    assert hits[0].metadata["source"] == "faq"
    assert hits[0].score > 0


def test_inmemory_reload_is_noop_but_callable() -> None:
    store = InMemoryVectorStore()
    store.add_documents(
        [{"content": "hello world", "metadata": {}}]
    )
    before = store.health().document_count
    store.reload()
    assert store.health().document_count == before
