"""Integration: register → login → refresh → logout (offline)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.integration.helpers import assert_ok
from tests.integration.helpers import bearer
from tests.integration.helpers import login
from tests.integration.helpers import register


@pytest.mark.asyncio
async def test_auth_register_login_refresh_logout(
    client: AsyncClient,
) -> None:
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "Secret123!"

    registered = await register(
        client,
        email=email,
        password=password,
    )
    assert registered["user"]["email"] == email
    assert registered["user"]["role"] == "user"
    assert registered["access_token"]

    me = await client.get(
        "/auth/me",
        headers=bearer(registered["access_token"]),
    )
    assert_ok(me)
    assert me.json()["email"] == email

    logged_in = await login(
        client,
        email=email,
        password=password,
    )
    assert logged_in["access_token"]

    refreshed = await client.post("/auth/refresh")
    assert_ok(refreshed)
    assert refreshed.json()["access_token"]
    new_token = refreshed.json()["access_token"]

    logged_out = await client.post(
        "/auth/logout",
        headers=bearer(new_token),
    )
    assert_ok(logged_out)
    assert logged_out.json()["status"] == "logged_out"

    # Refresh cookie should be cleared / revoked after logout.
    again = await client.post("/auth/refresh")
    assert again.status_code == 401
