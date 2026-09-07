"""Sliding-window rate limiter backed by Redis sorted sets."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any
from typing import Protocol

from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi import status

from app.redis_client import get_redis

logger = logging.getLogger(__name__)

# Policy defaults (attack surface: auth stuffing + abuse)
LOGIN_LIMIT = 5
LOGIN_WINDOW_SECONDS = 15 * 60
REGISTER_LIMIT = 3
REGISTER_WINDOW_SECONDS = 60 * 60
WS_MESSAGE_LIMIT = 20
WS_MESSAGE_WINDOW_SECONDS = 60
UPLOAD_LIMIT = 10
UPLOAD_WINDOW_SECONDS = 60 * 60


class AsyncRedisSorted(Protocol):
    async def zremrangebyscore(
        self, key: str, min: Any, max: Any
    ) -> Any: ...

    async def zcard(self, key: str) -> int: ...

    async def zadd(
        self, key: str, mapping: dict[str, float]
    ) -> Any: ...

    async def zrange(
        self,
        key: str,
        start: int,
        end: int,
        withscores: bool = False,
    ) -> Any: ...

    async def expire(self, key: str, time: int) -> Any: ...


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after: int
    remaining: int


class RateLimitExceeded(Exception):
    """Raised when a sliding window is exhausted."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, int(retry_after))
        super().__init__(
            f"Rate limit exceeded; retry after {self.retry_after}s"
        )


def http_429(retry_after: int) -> HTTPException:
    """Build a 429 with a Retry-After header for HTTP routes."""
    seconds = max(1, int(retry_after))
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded",
        headers={"Retry-After": str(seconds)},
    )


class SlidingWindowRateLimiter:
    """Count hits in a rolling window using a Redis ZSET."""

    def __init__(self, redis: AsyncRedisSorted) -> None:
        self._redis = redis

    async def hit(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        now: float | None = None,
    ) -> RateLimitResult:
        ts = time.time() if now is None else now
        window_start = ts - window_seconds
        redis_key = f"rl:{key}"

        await self._redis.zremrangebyscore(
            redis_key,
            0,
            window_start,
        )
        count = int(await self._redis.zcard(redis_key))
        if count >= limit:
            oldest = await self._redis.zrange(
                redis_key,
                0,
                0,
                withscores=True,
            )
            retry_after = window_seconds
            if oldest:
                oldest_ts = float(oldest[0][1])
                retry_after = max(
                    1,
                    int(oldest_ts + window_seconds - ts) + 1,
                )
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "event": "rate_limit_exceeded",
                    "key": key,
                    "limit": limit,
                    "retry_after": retry_after,
                },
            )
            return RateLimitResult(
                allowed=False,
                retry_after=retry_after,
                remaining=0,
            )

        member = f"{ts}:{uuid.uuid4().hex}"
        await self._redis.zadd(redis_key, {member: ts})
        await self._redis.expire(redis_key, window_seconds)
        remaining = max(0, limit - count - 1)
        return RateLimitResult(
            allowed=True,
            retry_after=0,
            remaining=remaining,
        )

    async def hit_or_raise(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        result = await self.hit(
            key,
            limit=limit,
            window_seconds=window_seconds,
        )
        if not result.allowed:
            raise RateLimitExceeded(result.retry_after)
        return result


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def rate_limit_dependency(
    *,
    scope: str,
    limit: int,
    window_seconds: int,
):
    """FastAPI dependency factory: limit by client IP."""

    async def _dependency(request: Request) -> None:
        redis = await get_redis()
        limiter = SlidingWindowRateLimiter(redis)
        key = f"{scope}:{client_ip(request)}"
        result = await limiter.hit(
            key,
            limit=limit,
            window_seconds=window_seconds,
        )
        if not result.allowed:
            raise http_429(result.retry_after)

    return Depends(_dependency)


async def enforce_user_rate_limit(
    *,
    scope: str,
    user_id: str,
    limit: int,
    window_seconds: int,
) -> None:
    """Enforce a per-user limit (upload / websocket)."""
    redis = await get_redis()
    limiter = SlidingWindowRateLimiter(redis)
    result = await limiter.hit(
        f"{scope}:{user_id}",
        limit=limit,
        window_seconds=window_seconds,
    )
    if not result.allowed:
        raise RateLimitExceeded(result.retry_after)
