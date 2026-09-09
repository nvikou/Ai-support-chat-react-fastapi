"""Tests for async knowledge ingest status transitions."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base
from app.models import KnowledgeDocument
from app.services import ingest_jobs
from app.services.ingest_jobs import STATUS_FAILED
from app.services.ingest_jobs import STATUS_INDEXED
from app.services.ingest_jobs import STATUS_PENDING
from app.services.ingest_jobs import run_knowledge_ingest


@pytest.fixture
async def db_session(tmp_path, monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )
    monkeypatch.setattr(
        ingest_jobs,
        "AsyncSessionLocal",
        session_factory,
    )
    async with session_factory() as session:
        yield session, tmp_path
    await engine.dispose()


@pytest.mark.asyncio
async def test_ingest_pending_becomes_indexed(
    db_session,
) -> None:
    session, tmp_path = db_session
    held = tmp_path / "doc.txt"
    held.write_text("hello knowledge", encoding="utf-8")
    doc = KnowledgeDocument(
        filename="doc.txt",
        content_hash="abc",
        status=STATUS_PENDING,
        storage_path=str(held),
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    async def fake_ingest(path: str, name: str) -> int:
        assert path == str(held)
        assert name == "doc.txt"
        return 3

    await run_knowledge_ingest(doc.id, ingest_fn=fake_ingest)
    await session.refresh(doc)
    assert doc.status == STATUS_INDEXED
    assert doc.chunk_count == 3
    assert doc.error_message is None
    assert not held.exists()


@pytest.mark.asyncio
async def test_ingest_failure_becomes_failed_with_message(
    db_session,
) -> None:
    session, tmp_path = db_session
    held = tmp_path / "bad.pdf"
    held.write_bytes(b"%PDF-1.4\n")
    doc = KnowledgeDocument(
        filename="bad.pdf",
        content_hash="def",
        status=STATUS_PENDING,
        storage_path=str(held),
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    async def boom(path: str, name: str) -> int:
        raise RuntimeError("parse exploded")

    await run_knowledge_ingest(doc.id, ingest_fn=boom)
    await session.refresh(doc)
    assert doc.status == STATUS_FAILED
    assert "parse exploded" in (doc.error_message or "")
