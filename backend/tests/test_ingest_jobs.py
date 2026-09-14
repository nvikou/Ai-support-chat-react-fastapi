"""Tests for async knowledge ingest status transitions."""

from __future__ import annotations

import asyncio

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


async def _pending_doc(
    session,
    *,
    filename: str,
    content_hash: str,
    storage_path: str | None,
) -> KnowledgeDocument:
    doc = KnowledgeDocument(
        filename=filename,
        content_hash=content_hash,
        status=STATUS_PENDING,
        storage_path=storage_path,
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc


@pytest.mark.asyncio
async def test_ingest_pending_becomes_indexed(
    db_session,
) -> None:
    session, tmp_path = db_session
    held = tmp_path / "doc.txt"
    held.write_text("hello knowledge", encoding="utf-8")
    doc = await _pending_doc(
        session,
        filename="doc.txt",
        content_hash="abc",
        storage_path=str(held),
    )

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
    doc = await _pending_doc(
        session,
        filename="bad.pdf",
        content_hash="def",
        storage_path=str(held),
    )

    async def boom(path: str, name: str) -> int:
        raise RuntimeError("parse exploded")

    await run_knowledge_ingest(doc.id, ingest_fn=boom)
    await session.refresh(doc)
    assert doc.status == STATUS_FAILED
    assert "parse exploded" in (doc.error_message or "")


@pytest.mark.asyncio
async def test_ingest_missing_file_marks_failed(
    db_session,
) -> None:
    session, tmp_path = db_session
    missing = tmp_path / "gone.txt"
    doc = await _pending_doc(
        session,
        filename="gone.txt",
        content_hash="missing",
        storage_path=str(missing),
    )

    called = False

    async def should_not_run(path: str, name: str) -> int:
        nonlocal called
        called = True
        return 1

    await run_knowledge_ingest(
        doc.id,
        ingest_fn=should_not_run,
    )
    await session.refresh(doc)
    assert called is False
    assert doc.status == STATUS_FAILED
    assert "missing on disk" in (doc.error_message or "").lower()


@pytest.mark.asyncio
async def test_ingest_skips_non_pending_document(
    db_session,
) -> None:
    session, tmp_path = db_session
    held = tmp_path / "done.txt"
    held.write_text("already indexed", encoding="utf-8")
    doc = await _pending_doc(
        session,
        filename="done.txt",
        content_hash="done",
        storage_path=str(held),
    )
    doc.status = STATUS_INDEXED
    doc.chunk_count = 9
    await session.commit()

    async def boom(path: str, name: str) -> int:
        raise AssertionError("must not re-ingest")

    await run_knowledge_ingest(doc.id, ingest_fn=boom)
    await session.refresh(doc)
    assert doc.status == STATUS_INDEXED
    assert doc.chunk_count == 9
    assert held.exists()


@pytest.mark.asyncio
async def test_parallel_ingest_jobs_keep_independent_status(
    db_session,
) -> None:
    """Two jobs must not clobber each other's terminal status."""
    session, tmp_path = db_session
    ok_path = tmp_path / "ok.txt"
    bad_path = tmp_path / "bad.txt"
    ok_path.write_text("good", encoding="utf-8")
    bad_path.write_text("bad", encoding="utf-8")

    ok_doc = await _pending_doc(
        session,
        filename="ok.txt",
        content_hash="ok",
        storage_path=str(ok_path),
    )
    bad_doc = await _pending_doc(
        session,
        filename="bad.txt",
        content_hash="bad",
        storage_path=str(bad_path),
    )

    async def ingest_ok(path: str, name: str) -> int:
        await asyncio.sleep(0.05)
        return 2

    async def ingest_bad(path: str, name: str) -> int:
        await asyncio.sleep(0.05)
        raise RuntimeError("chunker failed")

    await asyncio.gather(
        run_knowledge_ingest(ok_doc.id, ingest_fn=ingest_ok),
        run_knowledge_ingest(bad_doc.id, ingest_fn=ingest_bad),
    )

    await session.refresh(ok_doc)
    await session.refresh(bad_doc)
    assert ok_doc.status == STATUS_INDEXED
    assert ok_doc.chunk_count == 2
    assert bad_doc.status == STATUS_FAILED
    assert "chunker failed" in (bad_doc.error_message or "")


@pytest.mark.asyncio
async def test_faq_ingest_pending_becomes_indexed(
    db_session,
) -> None:
    import json

    from app.services.ingest_jobs import run_faq_ingest

    session, tmp_path = db_session
    held = tmp_path / "faq.json"
    entries = [
        {
            "question": "Hours?",
            "answer": "9-5",
            "category": "general",
        }
    ]
    held.write_text(
        json.dumps(entries),
        encoding="utf-8",
    )
    doc = await _pending_doc(
        session,
        filename="faq-batch-1.json",
        content_hash="faqhash",
        storage_path=str(held),
    )

    async def fake_faq(items: list) -> int:
        assert items[0]["question"] == "Hours?"
        return len(items)

    await run_faq_ingest(doc.id, ingest_fn=fake_faq)
    await session.refresh(doc)
    assert doc.status == STATUS_INDEXED
    assert doc.chunk_count == 1
    assert not held.exists()
