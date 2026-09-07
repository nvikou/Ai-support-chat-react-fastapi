"""Regression: sliding-window rate limits must trip and expose Retry-After.

Attack vector: unbounded login/register/upload/WS traffic enables
credential stuffing and resource exhaustion.
"""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from app.services.rate_limit import RateLimitExceeded
from app.services.rate_limit import SlidingWindowRateLimiter
from app.services.rate_limit import http_429


@pytest.fixture
async def redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def limiter(redis) -> SlidingWindowRateLimiter:
    return SlidingWindowRateLimiter(redis)


@pytest.mark.asyncio
async def test_allows_under_limit(
    limiter: SlidingWindowRateLimiter,
) -> None:
    for _ in range(5):
        result = await limiter.hit(
            "login:1.1.1.1",
            limit=5,
            window_seconds=900,
        )
        assert result.allowed is True


@pytest.mark.asyncio
async def test_blocks_sixth_login_attempt(
    limiter: SlidingWindowRateLimiter,
) -> None:
    key = "login:9.9.9.9"
    for _ in range(5):
        await limiter.hit(key, limit=5, window_seconds=900)
    denied = await limiter.hit(key, limit=5, window_seconds=900)
    assert denied.allowed is False
    assert denied.retry_after >= 1


@pytest.mark.asyncio
async def test_register_limit_three_per_hour(
    limiter: SlidingWindowRateLimiter,
) -> None:
    key = "register:2.2.2.2"
    for _ in range(3):
        assert (
            await limiter.hit(key, limit=3, window_seconds=3600)
        ).allowed
    denied = await limiter.hit(key, limit=3, window_seconds=3600)
    assert denied.allowed is False


@pytest.mark.asyncio
async def test_ws_message_limit_twenty_per_minute(
    limiter: SlidingWindowRateLimiter,
) -> None:
    key = "ws:user-42"
    for _ in range(20):
        assert (
            await limiter.hit(key, limit=20, window_seconds=60)
        ).allowed
    denied = await limiter.hit(key, limit=20, window_seconds=60)
    assert denied.allowed is False


@pytest.mark.asyncio
async def test_upload_limit_ten_per_hour(
    limiter: SlidingWindowRateLimiter,
) -> None:
    key = "upload:admin-1"
    for _ in range(10):
        assert (
            await limiter.hit(key, limit=10, window_seconds=3600)
        ).allowed
    denied = await limiter.hit(key, limit=10, window_seconds=3600)
    assert denied.allowed is False


@pytest.mark.asyncio
async def test_separate_keys_do_not_share_budget(
    limiter: SlidingWindowRateLimiter,
) -> None:
    for _ in range(5):
        await limiter.hit("login:a", limit=5, window_seconds=900)
    other = await limiter.hit("login:b", limit=5, window_seconds=900)
    assert other.allowed is True


def test_http_429_includes_retry_after_header() -> None:
    exc = http_429(retry_after=42)
    assert exc.status_code == 429
    assert exc.headers is not None
    assert exc.headers.get("Retry-After") == "42"


@pytest.mark.asyncio
async def test_hit_or_raise_raises_rate_limit_exceeded(
    limiter: SlidingWindowRateLimiter,
) -> None:
    key = "login:raise"
    for _ in range(5):
        await limiter.hit_or_raise(key, limit=5, window_seconds=900)
    with pytest.raises(RateLimitExceeded) as info:
        await limiter.hit_or_raise(key, limit=5, window_seconds=900)
    assert info.value.retry_after >= 1
