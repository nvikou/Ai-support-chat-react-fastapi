"""One-time WebSocket auth tickets backed by Redis.

JWT must never appear in WebSocket query strings: proxies and access
logs retain URLs. Short-lived opaque tickets limit that blast radius.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any
from typing import Protocol

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 60
KEY_PREFIX = "ws_ticket:"


class AsyncRedisLike(Protocol):
    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> Any: ...

    async def get(self, key: str) -> str | bytes | None: ...

    async def delete(self, *keys: str) -> Any: ...


class WsTicketStore:
    """Issue and atomically consume opaque WS tickets."""

    def __init__(
        self,
        redis: AsyncRedisLike,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds

    def key_for(self, ticket: str) -> str:
        return f"{KEY_PREFIX}{ticket}"

    async def issue(self, user_id: str) -> str:
        ticket = secrets.token_urlsafe(32)
        await self.redis.set(
            self.key_for(ticket),
            user_id,
            ex=self.ttl_seconds,
            nx=True,
        )
        logger.info(
            "ws_ticket_issued",
            extra={
                "event": "ws_ticket_issued",
                "user_id": user_id,
                "ttl_seconds": self.ttl_seconds,
            },
        )
        return ticket

    async def consume(
        self,
        ticket: str,
        *,
        expected_user_id: str | None = None,
    ) -> str | None:
        """Return bound user_id once; reject replay/expiry/mismatch.

        On user mismatch the ticket is left intact so the rightful
        owner can still connect (attacker probes must not burn it).
        """
        if not ticket:
            return None
        key = self.key_for(ticket)
        raw = await self.redis.get(key)
        if raw is None:
            return None
        user_id = raw.decode() if isinstance(raw, bytes) else str(raw)
        if (
            expected_user_id is not None
            and user_id != expected_user_id
        ):
            logger.warning(
                "ws_ticket_user_mismatch",
                extra={
                    "event": "ws_ticket_user_mismatch",
                    "expected_user_id": expected_user_id,
                    "ticket_user_id": user_id,
                },
            )
            return None
        await self.redis.delete(key)
        logger.info(
            "ws_ticket_consumed",
            extra={
                "event": "ws_ticket_consumed",
                "user_id": user_id,
            },
        )
        return user_id
