"""Shared helpers for offline HTTP integration tests."""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient
from httpx import Response


async def register(
    client: AsyncClient,
    *,
    email: str,
    password: str = "Secret123!",
    full_name: str = "Test User",
) -> dict[str, Any]:
    response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def login(
    client: AsyncClient,
    *,
    email: str,
    password: str,
) -> dict[str, Any]:
    response = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def admin_token(client: AsyncClient) -> str:
    data = await login(
        client,
        email="admin@example.com",
        password="test-admin-password",
    )
    return str(data["access_token"])


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def ws_ticket(client: AsyncClient, token: str) -> str:
    response = await client.post(
        "/auth/ws-ticket",
        headers=bearer(token),
    )
    assert response.status_code == 200, response.text
    return str(response.json()["ticket"])


def assert_ok(response: Response, status: int = 200) -> dict[str, Any]:
    assert response.status_code == status, response.text
    if response.content:
        return response.json()
    return {}
