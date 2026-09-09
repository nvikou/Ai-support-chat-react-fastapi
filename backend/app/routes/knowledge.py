import os
import shutil
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import get_agent
from app.config import get_settings
from app.database import get_db
from app.deps import require_admin
from app.models import KnowledgeDocument, User
from app.services.ingest_jobs import STATUS_PENDING
from app.services.ingest_jobs import run_knowledge_ingest
from app.services.rate_limit import UPLOAD_LIMIT
from app.services.rate_limit import UPLOAD_WINDOW_SECONDS
from app.services.rate_limit import RateLimitExceeded
from app.services.rate_limit import enforce_user_rate_limit
from app.services.rate_limit import http_429
from app.services.upload_security import UploadTooLargeError
from app.services.upload_security import UploadTypeRejectedError
from app.services.upload_security import save_upload_streaming

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
settings = get_settings()

# Durable holding area until BackgroundTasks finish ingest.
PENDING_UPLOAD_DIR = Path("./uploads/pending")


class FAQEntry(BaseModel):
    question: str
    answer: str
    category: str = "general"


class FAQBatch(BaseModel):
    entries: list[FAQEntry]


def _doc_payload(doc: KnowledgeDocument) -> dict:
    return {
        "id": doc.id,
        "filename": doc.filename,
        "chunk_count": doc.chunk_count,
        "status": doc.status,
        "error_message": doc.error_message,
        "uploaded_at": doc.uploaded_at.isoformat(),
    }


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Accept a file and schedule ingest off the request path.

    Why BackgroundTasks (for now): keeps the HTTP worker responsive
    without standing up Celery/ARQ. Why that is not enough later:
    tasks die with the process, are invisible to other workers, and
    have no durable retry — migrate to a Redis/Postgres queue before
    scaling beyond one app instance.
    """
    try:
        await enforce_user_rate_limit(
            scope="upload",
            user_id=admin.id,
            limit=UPLOAD_LIMIT,
            window_seconds=UPLOAD_WINDOW_SECONDS,
        )
    except RateLimitExceeded as exc:
        raise http_429(exc.retry_after) from exc

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file provided",
        )

    try:
        saved = await save_upload_streaming(
            file,
            max_bytes=settings.upload_max_bytes,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc
    except UploadTypeRejectedError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.content_hash == saved.content_hash
        )
    )
    if result.scalar_one_or_none():
        os.unlink(saved.path)
        raise HTTPException(
            status_code=409,
            detail="Document already uploaded",
        )

    PENDING_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    held_path = PENDING_UPLOAD_DIR / (
        f"{saved.content_hash}{saved.suffix}"
    )
    shutil.move(saved.path, held_path)

    doc = KnowledgeDocument(
        filename=file.filename,
        content_hash=saved.content_hash,
        chunk_count=0,
        status=STATUS_PENDING,
        storage_path=str(held_path),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    background_tasks.add_task(run_knowledge_ingest, doc.id)

    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "message": "Ingest scheduled",
    }


@router.get("/documents/{document_id}/status")
async def document_status(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Not found")
    return _doc_payload(doc)


@router.post("/faq")
async def add_faq(
    batch: FAQBatch,
    _: User = Depends(require_admin),
):
    agent = get_agent()
    count = await agent.add_faq_entries(
        [e.model_dump() for e in batch.entries]
    )
    return {"entries_added": count}


@router.get("/documents")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(KnowledgeDocument).order_by(
            KnowledgeDocument.uploaded_at.desc()
        )
    )
    docs = result.scalars().all()
    return [_doc_payload(d) for d in docs]
