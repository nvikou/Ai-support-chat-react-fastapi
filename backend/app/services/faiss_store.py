"""FAISS-backed VectorStore with locked, atomic on-disk writes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.services.atomic_index import atomic_publish_index
from app.services.atomic_index import prepare_staging_dir
from app.services.confidence import distance_to_similarity
from app.services.faiss_integrity import FaissIntegrityError
from app.services.faiss_integrity import verify_index_digest
from app.services.file_lock import InterprocessFileLock
from app.services.index_mtime import IndexMtimeWatcher
from app.services.vector_store import ScoredDocument
from app.services.vector_store import VectorStoreHealth

logger = logging.getLogger(__name__)

LOCK_NAME = ".index.lock"
DEFAULT_MTIME_TTL_SECONDS = 3.0


class FAISSVectorStore:
    """In-memory FAISS reads; durable writes under an inter-process lock.

    Concurrent HTTP ingest must not interleave ``add_documents`` and
    ``save_local``. Staging + ``os.replace`` keeps a crash from leaving
    a half-written live index.
    """

    def __init__(
        self,
        embeddings: Embeddings,
        persist_dir: str | Path,
        *,
        mtime_ttl_seconds: float = DEFAULT_MTIME_TTL_SECONDS,
    ) -> None:
        self._embeddings = embeddings
        self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._lock = InterprocessFileLock(
            self._persist_dir / LOCK_NAME
        )
        self._mtime = IndexMtimeWatcher(
            self._persist_dir,
            ttl_seconds=mtime_ttl_seconds,
        )
        self._store: FAISS | None = None
        self.reload()

    def search(
        self,
        query: str,
        *,
        k: int = 5,
    ) -> list[ScoredDocument]:
        # Other workers may have published a newer index on disk.
        if self._mtime.should_reload():
            logger.info(
                "faiss_mtime_reload",
                extra={
                    "event": "faiss_mtime_reload",
                    "path": str(self._persist_dir),
                },
            )
            self.reload()
        store = self._require_store()
        pairs = store.similarity_search_with_score(query, k=k)
        return [
            ScoredDocument(
                content=doc.page_content,
                metadata=dict(doc.metadata or {}),
                score=distance_to_similarity(score),
            )
            for doc, score in pairs
        ]

    def add_documents(
        self,
        documents: list[dict[str, Any]],
    ) -> int:
        if not documents:
            return 0
        docs = [
            Document(
                page_content=str(item.get("content", "")),
                metadata=dict(item.get("metadata") or {}),
            )
            for item in documents
        ]
        with self._lock:
            store = self._require_store()
            store.add_documents(docs)
            staging = prepare_staging_dir(self._persist_dir)
            store.save_local(str(staging))
            atomic_publish_index(staging, self._persist_dir)
            # Re-bind memory to the published tree.
            self._load_from_disk()
        return len(docs)

    def reload(self) -> None:
        with self._lock:
            self._load_from_disk()

    def health(self) -> VectorStoreHealth:
        ready = self._store is not None
        count = 0
        detail = ""
        if ready and self._store is not None:
            try:
                count = int(
                    self._store.index.ntotal  # type: ignore[attr-defined]
                )
            except Exception as exc:
                detail = str(exc)
                ready = False
        return VectorStoreHealth(
            backend="faiss",
            document_count=count,
            ready=ready,
            detail=detail,
        )

    def _require_store(self) -> FAISS:
        if self._store is None:
            raise RuntimeError("FAISS store is not loaded")
        return self._store

    def _load_from_disk(self) -> None:
        index_file = self._persist_dir / "index.faiss"
        if not index_file.exists():
            dummy = Document(
                page_content="VateCon AI Support initialized.",
                metadata={"source": "system"},
            )
            staging = prepare_staging_dir(self._persist_dir)
            store = FAISS.from_documents(
                [dummy],
                self._embeddings,
            )
            store.save_local(str(staging))
            atomic_publish_index(staging, self._persist_dir)
            self._store = store
            self._mtime.mark_loaded()
            return

        try:
            verify_index_digest(self._persist_dir)
        except FaissIntegrityError:
            logger.exception(
                "faiss_integrity_refused_load",
                extra={
                    "event": "faiss_integrity_refused_load",
                    "path": str(self._persist_dir),
                },
            )
            raise

        # LangChain still requires this flag to unpickle index.pkl;
        # digest verification above is the integrity gate. See SECURITY.md.
        self._store = FAISS.load_local(
            str(self._persist_dir),
            self._embeddings,
            allow_dangerous_deserialization=True,
        )
        self._mtime.mark_loaded()
