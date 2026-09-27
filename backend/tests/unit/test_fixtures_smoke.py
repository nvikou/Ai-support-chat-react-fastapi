"""Prove shared offline fixtures boot without network or Docker."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.fakes import OfflineAgent


@pytest.mark.asyncio
async def test_health_via_async_client(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_offline_agent_answers_from_memory(
    offline_agent: OfflineAgent,
) -> None:
    result = await offline_agent.answer("refund policy", [])
    assert "30 days" in result["answer"]
    assert result["degraded"] is False
    assert result["sources"]
