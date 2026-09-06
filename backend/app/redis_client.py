"""Shared async Redis connection for tickets and rate limits."""

from __future__ import annotations

from redis.asyncio import Redis

from app.config import get_settings

_redis: Redis | None = None


async def get_redis() -> Redis:
    """Return a process-wide async Redis client."""
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
