"""Offline tests for resilient LLM client behaviour."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from dataclasses import field

import pytest

from app.exceptions import CircuitOpen
from app.exceptions import LLMError
from app.exceptions import LLMRateLimited
from app.exceptions import LLMTimeout
from app.services.llm_client import InMemoryCircuitBreaker
from app.services.llm_client import LLMClient


@dataclass
class FakeSettings:
    openai_model: str = "gpt-4o"
    openai_fallback_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 0.05
    openai_max_retries: int = 3
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_seconds: float = 60.0


class FakeHTTPError(Exception):
    """Stand-in for provider HTTP errors (no network)."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}")


@dataclass
class FakeClock:
    now: float = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class RecordingSleep:
    delays: list[float] = field(default_factory=list)

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def _client(
    settings: FakeSettings | None = None,
    *,
    threshold: int | None = None,
    reset_seconds: float | None = None,
    clock: FakeClock | None = None,
) -> tuple[LLMClient, RecordingSleep, FakeClock]:
    cfg = settings or FakeSettings()
    if threshold is not None:
        cfg.circuit_breaker_threshold = threshold
    if reset_seconds is not None:
        cfg.circuit_breaker_reset_seconds = reset_seconds
    fake_clock = clock or FakeClock()
    sleep = RecordingSleep()
    circuit = InMemoryCircuitBreaker(
        threshold=cfg.circuit_breaker_threshold,
        reset_seconds=cfg.circuit_breaker_reset_seconds,
        clock=fake_clock,
    )
    client = LLMClient(
        cfg,  # type: ignore[arg-type]
        circuit=circuit,
        sleep=sleep,
        clock=fake_clock,
    )
    return client, sleep, fake_clock


@pytest.mark.asyncio
async def test_retries_on_429_then_succeeds() -> None:
    client, sleep, _ = _client()
    calls: list[str] = []

    async def operation(model: str) -> str:
        calls.append(model)
        if len(calls) == 1:
            raise FakeHTTPError(429)
        return "ok"

    result = await client.invoke(operation)

    assert result.value == "ok"
    assert result.degraded is False
    assert len(calls) == 2
    assert len(sleep.delays) == 1


@pytest.mark.asyncio
async def test_no_retry_on_400() -> None:
    client, sleep, _ = _client()
    calls = 0

    async def operation(model: str) -> str:
        nonlocal calls
        calls += 1
        raise FakeHTTPError(400)

    with pytest.raises(LLMError) as exc_info:
        await client.invoke(operation)

    assert calls == 1
    assert sleep.delays == []
    assert not isinstance(
        exc_info.value,
        (LLMTimeout, LLMRateLimited),
    )


@pytest.mark.asyncio
async def test_exhausted_retries_switch_to_fallback() -> None:
    client, _, _ = _client(
        FakeSettings(openai_max_retries=2),
    )
    calls: list[str] = []

    async def operation(model: str) -> str:
        calls.append(model)
        if model == "gpt-4o":
            raise FakeHTTPError(503)
        return "fallback-ok"

    result = await client.invoke(operation)

    assert result.value == "fallback-ok"
    assert result.degraded is True
    assert result.model == "gpt-4o-mini"
    assert calls.count("gpt-4o") == 2
    assert calls.count("gpt-4o-mini") == 1


@pytest.mark.asyncio
async def test_fallback_failure_opens_circuit_after_threshold() -> None:
    client, _, _ = _client(threshold=2)

    async def always_fail(model: str) -> str:
        raise FakeHTTPError(503)

    with pytest.raises(LLMError):
        await client.invoke(always_fail)
    with pytest.raises(LLMError):
        await client.invoke(always_fail)

    with pytest.raises(CircuitOpen):
        await client.invoke(always_fail)


@pytest.mark.asyncio
async def test_circuit_resets_after_cooldown() -> None:
    clock = FakeClock()
    client, _, _ = _client(
        threshold=1,
        reset_seconds=10.0,
        clock=clock,
    )

    async def fail(model: str) -> str:
        raise FakeHTTPError(500)

    async def ok(model: str) -> str:
        return "recovered"

    with pytest.raises(LLMError):
        await client.invoke(fail)

    with pytest.raises(CircuitOpen):
        await client.invoke(ok)

    clock.advance(10.0)
    result = await client.invoke(ok)
    assert result.value == "recovered"
    assert client.circuit.is_open is False


@pytest.mark.asyncio
async def test_timeout_is_propagated_as_llm_timeout() -> None:
    client, sleep, _ = _client(
        FakeSettings(
            openai_timeout_seconds=0.01,
            openai_max_retries=1,
            openai_fallback_model="gpt-4o",
        ),
    )

    async def slow(model: str) -> str:
        await asyncio.sleep(0.05)
        return "too-late"

    with pytest.raises(LLMTimeout):
        await client.invoke(slow)

    assert sleep.delays == []
