import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.database import get_db
from app.deps import require_admin
from app.models import KnowledgeDocument, User
from app.agent import get_agent
from app.services.upload_security import UploadTooLargeError
from app.services.upload_security import UploadTypeRejectedError
from app.services.upload_security import save_upload_streaming
from pydantic import BaseModel

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
settings = get_settings()


class FAQEntry(BaseModel):
    question: str
    answer: str
    category: str = "general"


class FAQBatch(BaseModel):
    entries: list[FAQEntry]


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

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

    try:
        agent = get_agent()
        chunk_count = await agent.ingest_document(
            saved.path,
            file.filename,
        )
    finally:
        os.unlink(saved.path)

    doc = KnowledgeDocument(
        filename=file.filename,
        content_hash=saved.content_hash,
        chunk_count=chunk_count,
    )
    db.add(doc)
    await db.commit()

    return {"filename": file.filename, "chunks_indexed": chunk_count}


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
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "chunk_count": d.chunk_count,
            "uploaded_at": d.uploaded_at.isoformat(),
        }
        for d in docs
    ]
