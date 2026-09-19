"""Integration: knowledge upload / FAQ / list (admin, offline)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.integration.helpers import admin_token
from tests.integration.helpers import assert_ok
from tests.integration.helpers import bearer


@pytest.mark.asyncio
async def test_faq_ingest_accepted_and_listed(
    client: AsyncClient,
) -> None:
    token = await admin_token(client)
    headers = bearer(token)

    payload = {
        "entries": [
            {
                "question": f"Hours {uuid.uuid4().hex[:6]}?",
                "answer": "We are open 9-5.",
                "category": "general",
            }
        ]
    }
    created = await client.post(
        "/knowledge/faq",
        headers=headers,
        json=payload,
    )
    body = assert_ok(created, status=202)
    assert body["status"] == "pending"
    doc_id = body["id"]

    # BackgroundTasks run after the response on the ASGI app;
    # poll status until indexed (OfflineAgent is synchronous/fast).
    status_body: dict = {}
    for _ in range(20):
        status = await client.get(
            f"/knowledge/documents/{doc_id}/status",
            headers=headers,
        )
        status_body = assert_ok(status)
        if status_body["status"] in {"indexed", "failed"}:
            break

    assert status_body["status"] == "indexed"
    assert status_body["chunk_count"] >= 1

    listed = await client.get(
        "/knowledge/documents",
        headers=headers,
    )
    docs = assert_ok(listed)
    assert any(doc["id"] == doc_id for doc in docs)


@pytest.mark.asyncio
async def test_knowledge_requires_admin(
    client: AsyncClient,
) -> None:
    from tests.integration.helpers import register

    user = await register(
        client,
        email=f"kb-{uuid.uuid4().hex[:8]}@example.com",
    )
    response = await client.get(
        "/knowledge/documents",
        headers=bearer(user["access_token"]),
    )
    assert response.status_code == 403
