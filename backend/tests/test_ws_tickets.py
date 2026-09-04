"""Regression tests: WebSocket auth must use one-time Redis tickets.

Attack vector covered: JWT in ?token= leaks via access logs, proxies,
and browser history. Tickets must be opaque, single-use, short-lived,
and bound to the issuing user.
"""

from __future__ import annotations

import pytest

from app.services.ws_tickets import WsTicketStore


class FakeRedis:
    """Minimal async Redis stand-in (no network)."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._ttl: dict[str, int] = {}

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool | None:
        if nx and key in self._data:
            return None
        self._data[key] = value
        if ex is not None:
            self._ttl[key] = ex
        return True

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                self._ttl.pop(key, None)
                removed += 1
        return removed

    async def getdel(self, key: str) -> str | None:
        value = self._data.get(key)
        if value is not None:
            del self._data[key]
            self._ttl.pop(key, None)
        return value

    def expire_key(self, key: str) -> None:
        """Simulate TTL expiry for tests."""
        self._data.pop(key, None)
        self._ttl.pop(key, None)


@pytest.fixture
def store() -> WsTicketStore:
    return WsTicketStore(FakeRedis(), ttl_seconds=60)


@pytest.mark.asyncio
async def test_valid_ticket_is_accepted(store: WsTicketStore) -> None:
    ticket = await store.issue(user_id="user-a")
    consumed = await store.consume(ticket)
    assert consumed == "user-a"


@pytest.mark.asyncio
async def test_replayed_ticket_is_rejected(store: WsTicketStore) -> None:
    ticket = await store.issue(user_id="user-a")
    assert await store.consume(ticket) == "user-a"
    assert await store.consume(ticket) is None


@pytest.mark.asyncio
async def test_expired_ticket_is_rejected(store: WsTicketStore) -> None:
    ticket = await store.issue(user_id="user-a")
    key = store.key_for(ticket)
    store.redis.expire_key(key)  # type: ignore[attr-defined]
    assert await store.consume(ticket) is None


@pytest.mark.asyncio
async def test_ticket_bound_to_issuing_user(store: WsTicketStore) -> None:
    ticket = await store.issue(user_id="user-a")
    # Attacker presenting as another user must be refused.
    assert await store.consume(
        ticket,
        expected_user_id="user-b",
    ) is None
    # Rightful owner can still consume the untouched ticket.
    assert await store.consume(
        ticket,
        expected_user_id="user-a",
    ) == "user-a"
