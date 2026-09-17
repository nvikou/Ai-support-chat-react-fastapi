"""Offline doubles used by shared fixtures (no network I/O)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.llm_client import LLMCallResult
from app.services.vector_store import InMemoryVectorStore
from app.services.vector_store import VectorStore


class FakeLLMClient:
    """Satisfy ``LLMClient.invoke`` without calling a provider."""

    def __init__(self, answer: str = "Offline test answer.") -> None:
        self.answer = answer
        self.calls: list[str] = []

    async def invoke(
        self,
        operation: Any,
        *,
        primary_model: str | None = None,
        fallback_model: str | None = None,
    ) -> LLMCallResult:
        model = primary_model or "fake-primary"
        self.calls.append(model)
        value = await operation(model)
        return LLMCallResult(
            value=value,
            model=model,
            degraded=False,
        )


class OfflineAgent:
    """SupportAgent stand-in: in-memory retrieval, no OpenAI/FAISS."""

    def __init__(
        self,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.vector_store = vector_store or InMemoryVectorStore()
        if self.vector_store.health().document_count == 0:
            self.vector_store.add_documents(
                [
                    {
                        "content": (
                            "VateCon refunds are available "
                            "within 30 days of purchase."
                        ),
                        "metadata": {"source": "test-faq"},
                    }
                ]
            )

    async def answer(
        self,
        question: str,
        history: list[dict],
    ) -> dict[str, Any]:
        hits = self.vector_store.search(question, k=3)
        if hits:
            answer = hits[0].content
            confidence = 0.85
            sources = [
                str(h.metadata.get("source", "kb")) for h in hits
            ]
        else:
            answer = (
                "I do not have enough knowledge-base context "
                "for that question."
            )
            confidence = 0.2
            sources = []
        return {
            "answer": answer,
            "confidence": confidence,
            "confidence_band": (
                "high" if confidence >= 0.7 else "low"
            ),
            "confidence_signals": {},
            "sources": sources,
            "should_escalate": confidence < 0.5,
            "escalation_reason": (
                None if confidence >= 0.5 else "low confidence"
            ),
            "degraded": False,
        }

    async def ingest_document(
        self,
        file_path: str,
        filename: str,
    ) -> int:
        text = Path(file_path).read_text(
            encoding="utf-8",
            errors="ignore",
        )
        return self.vector_store.add_documents(
            [
                {
                    "content": text,
                    "metadata": {"source": filename},
                }
            ]
        )

    async def add_faq_entries(self, entries: list[dict]) -> int:
        docs = [
            {
                "content": (
                    f"Q: {e['question']}\nA: {e['answer']}"
                ),
                "metadata": {
                    "source": "FAQ",
                    "category": e.get("category", "general"),
                },
            }
            for e in entries
        ]
        return self.vector_store.add_documents(docs)
