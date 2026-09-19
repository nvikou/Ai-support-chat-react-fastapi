"""Integration: admin API authorization."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.integration.helpers import admin_token
from tests.integration.helpers import assert_ok
from tests.integration.helpers import bearer
from tests.integration.helpers import register


@pytest.mark.asyncio
async def test_non_admin_receives_403_on_stats(
    client: AsyncClient,
) -> None:
    user = await register(
        client,
        email=f"noadmin-{uuid.uuid4().hex[:8]}@example.com",
    )
    response = await client.get(
        "/admin/stats",
        headers=bearer(user["access_token"]),
    )
    assert response.status_code == 403
    assert "Admin" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_can_read_stats(
    client: AsyncClient,
) -> None:
    token = await admin_token(client)
    response = await client.get(
        "/admin/stats",
        headers=bearer(token),
    )
    body = assert_ok(response)
    assert "total_conversations" in body
    assert "total_users" in body


@pytest.mark.asyncio
async def test_non_admin_receives_403_on_users_list(
    client: AsyncClient,
) -> None:
    user = await register(
        client,
        email=f"nousers-{uuid.uuid4().hex[:8]}@example.com",
    )
    response = await client.get(
        "/admin/users",
        headers=bearer(user["access_token"]),
    )
    assert response.status_code == 403
