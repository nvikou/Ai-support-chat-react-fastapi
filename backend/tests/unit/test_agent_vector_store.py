"""Agent must talk to VectorStore, not raw LangChain FAISS."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agent import SupportAgent
from app.services.vector_store import InMemoryVectorStore


@pytest.mark.asyncio
async def test_add_faq_indexes_via_injected_store() -> None:
    store = InMemoryVectorStore()
    agent = SupportAgent(vector_store=store)

    added = await agent.add_faq_entries(
        [
            {
                "question": "How do refunds work?",
                "answer": "Within 30 days with receipt.",
                "category": "billing",
            }
        ]
    )

    assert added == 1
    assert store.health().document_count == 1
    hits = agent._retrieve("refunds", k=1)
    assert len(hits) == 1
    assert "30 days" in hits[0].content
    assert hits[0].metadata["source"] == "FAQ"


@pytest.mark.asyncio
async def test_ingest_document_indexes_via_store(
    tmp_path: Path,
) -> None:
    store = InMemoryVectorStore()
    agent = SupportAgent(vector_store=store)
    path = tmp_path / "policy.txt"
    path.write_text(
        "Warranty covers hardware for two years.",
        encoding="utf-8",
    )

    count = await agent.ingest_document(str(path), "policy.txt")

    assert count >= 1
    hits = store.search("warranty hardware", k=1)
    assert hits
    assert "two years" in hits[0].content
    assert hits[0].metadata.get("source") == "policy.txt"


def test_default_agent_uses_faiss_vector_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: dict[str, object] = {}

    class FakeFAISS:
        def __init__(self, embeddings, persist_dir, **kwargs):
            created["persist_dir"] = str(persist_dir)
            self._embeddings = embeddings

        def search(self, query, *, k=5):
            return []

        def add_documents(self, documents):
            return 0

        def reload(self) -> None:
            return None

        def health(self):
            from app.services.vector_store import VectorStoreHealth

            return VectorStoreHealth(
                backend="faiss",
                document_count=0,
                ready=True,
            )

    monkeypatch.setattr(
        "app.agent.FAISSVectorStore",
        FakeFAISS,
    )
    agent = SupportAgent()
    assert created["persist_dir"].endswith("faiss_db")
    assert agent.vector_store.health().backend == "faiss"
