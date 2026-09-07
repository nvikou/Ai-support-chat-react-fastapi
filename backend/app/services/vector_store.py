"""Vector store abstraction for retrieval and indexing.

FAISS remains the production backend; this Protocol lets tests use
an in-memory stand-in and keeps write/reload policy out of the agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Protocol
from typing import runtime_checkable


@dataclass(frozen=True)
class ScoredDocument:
    """One retrieval hit with a similarity-like score (higher=better)."""

    content: str
    metadata: dict[str, Any]
    score: float


@dataclass(frozen=True)
class VectorStoreHealth:
    """Lightweight health snapshot for ops and tests."""

    backend: str
    document_count: int
    ready: bool
    detail: str = ""


@runtime_checkable
class VectorStore(Protocol):
    """Read/write contract for knowledge-base embeddings."""

    def search(
        self,
        query: str,
        *,
        k: int = 5,
    ) -> list[ScoredDocument]:
        """Return top-k scored documents for ``query``."""
        ...

    def add_documents(
        self,
        documents: list[dict[str, Any]],
    ) -> int:
        """Index documents ``{content, metadata}``; return count added."""
        ...

    def reload(self) -> None:
        """Refresh in-memory state from the durable backend if any."""
        ...

    def health(self) -> VectorStoreHealth:
        """Report readiness and approximate document count."""
        ...


@dataclass
class InMemoryVectorStore:
    """Process-local store for unit tests (no disk, no embeddings).

    Similarity is a naive token-overlap score so tests stay offline
    and deterministic without OpenAI or FAISS.
    """

    _docs: list[dict[str, Any]] = field(default_factory=list)
    _generation: int = 0

    def search(
        self,
        query: str,
        *,
        k: int = 5,
    ) -> list[ScoredDocument]:
        tokens = set(query.lower().split())
        scored: list[ScoredDocument] = []
        for doc in self._docs:
            content = str(doc.get("content", ""))
            doc_tokens = set(content.lower().split())
            if not tokens:
                score = 0.0
            else:
                overlap = len(tokens & doc_tokens)
                score = overlap / len(tokens)
            scored.append(
                ScoredDocument(
                    content=content,
                    metadata=dict(doc.get("metadata") or {}),
                    score=score,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:k]

    def add_documents(
        self,
        documents: list[dict[str, Any]],
    ) -> int:
        for doc in documents:
            self._docs.append(
                {
                    "content": str(doc.get("content", "")),
                    "metadata": dict(doc.get("metadata") or {}),
                }
            )
        self._generation += 1
        return len(documents)

    def reload(self) -> None:
        # Nothing durable to reload; generation bump documents intent.
        self._generation += 1

    def health(self) -> VectorStoreHealth:
        return VectorStoreHealth(
            backend="memory",
            document_count=len(self._docs),
            ready=True,
            detail=f"generation={self._generation}",
        )
