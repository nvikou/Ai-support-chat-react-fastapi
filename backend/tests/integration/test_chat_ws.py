"""Integration: WebSocket chat auth and session isolation."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from starlette.testclient import TestClient

from tests.integration.helpers import register
from tests.integration.helpers import ws_ticket


@pytest.fixture
def sync_client(app):
    with TestClient(app) as client:
        yield client


@pytest.mark.asyncio
async def test_ws_chat_answers_with_offline_agent(
    client: AsyncClient,
    sync_client: TestClient,
) -> None:
    email = f"chat-{uuid.uuid4().hex[:8]}@example.com"
    auth = await register(client, email=email)
    ticket = await ws_ticket(client, auth["access_token"])
    session_id = str(uuid.uuid4())

    with sync_client.websocket_connect(
        f"/ws/chat/{session_id}?ticket={ticket}",
    ) as websocket:
        connected = websocket.receive_json()
        assert connected["type"] == "connected"
        assert connected["conversation_id"]

        websocket.send_json({"message": "Tell me about refunds"})
        typing = websocket.receive_json()
        assert typing["type"] == "typing"
        reply = websocket.receive_json()
        assert reply["type"] == "message"
        assert "30 days" in reply["content"]


@pytest.mark.asyncio
async def test_ws_rejects_other_users_session(
    client: AsyncClient,
    sync_client: TestClient,
) -> None:
    """A second user must not join another user's conversation."""
    owner = await register(
        client,
        email=f"owner-{uuid.uuid4().hex[:8]}@example.com",
    )
    intruder = await register(
        client,
        email=f"intruder-{uuid.uuid4().hex[:8]}@example.com",
    )
    session_id = str(uuid.uuid4())

    owner_ticket = await ws_ticket(client, owner["access_token"])
    with sync_client.websocket_connect(
        f"/ws/chat/{session_id}?ticket={owner_ticket}",
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json({"message": "hello from owner"})
        assert websocket.receive_json()["type"] == "typing"
        assert websocket.receive_json()["type"] == "message"

    other_ticket = await ws_ticket(client, intruder["access_token"])
    with sync_client.websocket_connect(
        f"/ws/chat/{session_id}?ticket={other_ticket}",
    ) as websocket:
        denied = websocket.receive_json()
        assert denied["type"] == "error"
        assert "Access denied" in denied["content"]


@pytest.mark.asyncio
async def test_ws_requires_valid_ticket(
    sync_client: TestClient,
) -> None:
    session_id = str(uuid.uuid4())
    with sync_client.websocket_connect(
        f"/ws/chat/{session_id}?ticket=not-a-real-ticket",
    ) as websocket:
        payload = websocket.receive_json()
        assert payload["type"] == "error"
        assert "Authentication" in payload["content"]
