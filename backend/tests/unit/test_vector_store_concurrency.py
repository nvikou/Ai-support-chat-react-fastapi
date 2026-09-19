"""Concurrency and durability tests for FAISSVectorStore."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from langchain_core.embeddings import Embeddings

from app.services.faiss_integrity import verify_index_digest
from app.services.faiss_store import FAISSVectorStore


class DeterministicEmbeddings(Embeddings):
    """Offline embeddings so concurrency tests never call OpenAI."""

    def __init__(self, dim: int = 32) -> None:
        self._dim = dim

    def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return [self._vec(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)

    def _vec(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        while len(values) < self._dim:
            for byte in digest:
                values.append((byte / 255.0) * 2.0 - 1.0)
                if len(values) >= self._dim:
                    break
            digest = hashlib.sha256(digest).digest()
        return values


def test_concurrent_adds_preserve_all_documents(
    tmp_path: Path,
) -> None:
    """Thread + file locks must serialize writers so no add is dropped."""
    store = FAISSVectorStore(
        DeterministicEmbeddings(),
        tmp_path,
        mtime_ttl_seconds=0.0,
    )
    workers = 6
    barrier = threading.Barrier(workers)
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            barrier.wait(timeout=10)
            store.add_documents(
                [
                    {
                        "content": (
                            f"concurrent topic-{index} "
                            f"unique-{index}"
                        ),
                        "metadata": {"source": f"w{index}"},
                    }
                ]
            )
        except BaseException as exc:  # noqa: BLE001 — collect
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=(i,))
        for i in range(workers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive()

    assert errors == []
    # Dummy bootstrap doc + one per worker.
    assert store.health().document_count == workers + 1
    verify_index_digest(tmp_path)

    for index in range(workers):
        needle = f"concurrent topic-{index} unique-{index}"
        hits = store.search(needle, k=workers + 1)
        assert any(hit.content == needle for hit in hits), (
            f"missing document for worker {index}: "
            f"{[h.content for h in hits]}"
        )


def test_second_store_instance_reloads_published_index(
    tmp_path: Path,
) -> None:
    """Peer process/worker must see docs published by another."""
    writer = FAISSVectorStore(
        DeterministicEmbeddings(),
        tmp_path,
        mtime_ttl_seconds=0.0,
    )
    writer.add_documents(
        [
            {
                "content": "shipping takes five business days",
                "metadata": {"source": "policy"},
            }
        ]
    )

    reader = FAISSVectorStore(
        DeterministicEmbeddings(),
        tmp_path,
        mtime_ttl_seconds=0.0,
    )
    hits = reader.search(
        "shipping takes five business days",
        k=3,
    )
    assert hits
    assert any(
        "five business days" in hit.content for hit in hits
    )
    assert reader.health().ready is True
