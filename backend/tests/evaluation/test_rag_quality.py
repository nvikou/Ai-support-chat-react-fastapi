"""RAG quality evaluation skeleton (PROMPT 7).

These checks are intentionally lightweight and offline. Expand with
golden Q/A pairs and retrieval metrics once a labeled set exists —
do not call live OpenAI from this module.
"""

from __future__ import annotations

import pytest

from app.services.vector_store import InMemoryVectorStore


@pytest.mark.evaluation
def test_rag_retrieval_skeleton_ranks_relevant_chunk() -> None:
    store = InMemoryVectorStore()
    store.add_documents(
        [
            {
                "content": "Refunds are available within 30 days.",
                "metadata": {"source": "policy"},
            },
            {
                "content": "Shipping takes five business days.",
                "metadata": {"source": "shipping"},
            },
        ]
    )
    hits = store.search("How do refunds work?", k=1)
    assert hits
    assert "Refunds" in hits[0].content
