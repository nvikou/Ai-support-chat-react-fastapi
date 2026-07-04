import hashlib
import tempfile
import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.deps import require_admin
from app.models import KnowledgeDocument, User
from app.agent import get_agent
from pydantic import BaseModel

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


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

    allowed_types = {"application/pdf", "text/plain", "text/markdown"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only PDF and text files are supported")

    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()

    # Check duplicate
    result = await db.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.content_hash == content_hash)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Document already uploaded")

    # Save to temp file and ingest
    suffix = ".pdf" if file.content_type == "application/pdf" else ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        agent = get_agent()
        chunk_count = await agent.ingest_document(tmp_path, file.filename)
    finally:
        os.unlink(tmp_path)

    doc = KnowledgeDocument(
        filename=file.filename,
        content_hash=content_hash,
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
    count = await agent.add_faq_entries([e.model_dump() for e in batch.entries])
    return {"entries_added": count}


@router.get("/documents")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(KnowledgeDocument).order_by(KnowledgeDocument.uploaded_at.desc()))
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
