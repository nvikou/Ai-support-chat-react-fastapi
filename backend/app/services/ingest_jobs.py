"""Background knowledge-base ingest jobs.

FastAPI BackgroundTasks are enough for a single process: the HTTP
handler returns 202 and work continues in-process. That is NOT enough
once we run multiple uvicorn workers or hosts — BackgroundTasks do not
survive process restarts, are not shared across workers, and provide
no retries/visibility. At that point replace this module's scheduler
with a real queue (Celery, ARQ, or RQ) backed by Redis/Postgres.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import KnowledgeDocument

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_INDEXED = "indexed"
STATUS_FAILED = "failed"

IngestFn = Callable[[str, str], Awaitable[int]]


async def _default_ingest(file_path: str, filename: str) -> int:
    from app.agent import get_agent

    return await get_agent().ingest_document(file_path, filename)


async def run_knowledge_ingest(
    document_id: int,
    *,
    ingest_fn: IngestFn | None = None,
) -> None:
    """Load a pending document from disk and mark indexed/failed.

    Designed so unit tests can inject ``ingest_fn`` without OpenAI.
    """
    ingest = ingest_fn or _default_ingest

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id
            )
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            logger.warning(
                "ingest_missing_document",
                extra={
                    "event": "ingest_missing_document",
                    "document_id": document_id,
                },
            )
            return
        if doc.status != STATUS_PENDING:
            return

        file_path = doc.storage_path
        if not file_path or not Path(file_path).is_file():
            doc.status = STATUS_FAILED
            doc.error_message = "Uploaded file missing on disk"
            await db.commit()
            return

        try:
            chunk_count = await ingest(file_path, doc.filename)
            doc.chunk_count = chunk_count
            doc.status = STATUS_INDEXED
            doc.error_message = None
            await db.commit()
            logger.info(
                "ingest_indexed",
                extra={
                    "event": "ingest_indexed",
                    "document_id": document_id,
                    "chunks": chunk_count,
                },
            )
        except Exception as exc:
            doc.status = STATUS_FAILED
            doc.error_message = str(exc)[:2000]
            await db.commit()
            logger.exception(
                "ingest_failed",
                extra={
                    "event": "ingest_failed",
                    "document_id": document_id,
                    "error_type": type(exc).__name__,
                },
            )
        finally:
            try:
                if file_path and os.path.exists(file_path):
                    os.unlink(file_path)
            except OSError:
                pass
