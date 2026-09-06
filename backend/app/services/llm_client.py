"""Resilient LLM invocation: timeout, retry, fallback, circuit."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from typing import TypeVar

from app.config import Settings
from app.config import get_settings
from app.exceptions import CircuitOpen
from app.exceptions import LLMError
from app.exceptions import LLMRateLimited
from app.exceptions import LLMTimeout
from app.exceptions import LLMUnavailable

logger = logging.getLogger(__name__)

T = TypeVar("T")

_TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_TRANSIENT_ERRORS = (LLMTimeout, LLMRateLimited, LLMUnavailable)

InvokeFn = Callable[[str], Awaitable[T]]


@dataclass(frozen=True)
class LLMCallResult:
    """Outcome of a resilient LLM invocation."""

    value: Any
    model: str
    degraded: bool = False


class InMemoryCircuitBreaker:
    """Trip after consecutive failures; cool down before retrying.

    State lives in process memory on purpose. Keep all mutations
    behind this class so a Redis-backed breaker can replace it later
    without changing LLMClient call sites.
    """

    def __init__(
        self,
        threshold: int,
        reset_seconds: float,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._threshold = threshold
        self._reset_seconds = reset_seconds
        self._clock = clock or time.monotonic
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        elapsed = self._clock() - self._opened_at
        return elapsed < self._reset_seconds

    def guard(self) -> None:
        """Raise CircuitOpen while the breaker is tripped."""
        if self._opened_at is None:
            return
        if self.is_open:
            raise CircuitOpen(
                "LLM circuit breaker is open; "
                "skipping provider call"
            )
        logger.info(
            "circuit_breaker_reset",
            extra={
                "event": "circuit_breaker_reset",
                "reset_seconds": self._reset_seconds,
            },
        )
        self._opened_at = None
        self._consecutive_failures = 0

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures < self._threshold:
            return
        self._opened_at = self._clock()
        logger.warning(
            "circuit_breaker_opened",
            extra={
                "event": "circuit_breaker_opened",
                "consecutive_failures": (
                    self._consecutive_failures
                ),
                "threshold": self._threshold,
                "reset_seconds": self._reset_seconds,
            },
        )


def _status_code(exc: BaseException) -> int | None:
    for attr in ("status_code", "http_status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code
    return None


def _is_timeout(exc: BaseException) -> bool:
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    return "timeout" in type(exc).__name__.lower()


def map_provider_error(exc: BaseException) -> LLMError:
    """Translate provider/SDK errors into our typed hierarchy."""
    if isinstance(exc, LLMError):
        return exc
    if _is_timeout(exc):
        return LLMTimeout("LLM call timed out", cause=exc)
    code = _status_code(exc)
    if code == 429:
        return LLMRateLimited(
            "LLM rate limited (429)",
            cause=exc,
        )
    if code in _TRANSIENT_STATUS_CODES:
        return LLMUnavailable(
            f"LLM provider unavailable ({code})",
            cause=exc,
        )
    return LLMError(f"LLM call failed: {exc}", cause=exc)


class LLMClient:
    """Wrap every LLM call with timeout, retry, fallback, circuit."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        circuit: InMemoryCircuitBreaker | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._sleep = sleep or asyncio.sleep
        self._clock = clock or time.monotonic
        self._circuit = circuit or InMemoryCircuitBreaker(
            threshold=self._settings.circuit_breaker_threshold,
            reset_seconds=(
                self._settings.circuit_breaker_reset_seconds
            ),
            clock=self._clock,
        )

    @property
    def circuit(self) -> InMemoryCircuitBreaker:
        return self._circuit

    async def invoke(
        self,
        operation: InvokeFn[T],
        *,
        primary_model: str | None = None,
        fallback_model: str | None = None,
    ) -> LLMCallResult:
        """Run ``operation(model)`` with resilience policies.

        ``operation`` receives the model name so callers can rebuild
        chains when falling back to a cheaper model.
        """
        primary = primary_model or self._settings.openai_model
        fallback = (
            fallback_model
            or self._settings.openai_fallback_model
        )

        self._circuit.guard()

        primary_error: LLMError | None = None
        try:
            value = await self._retry_call(operation, primary)
            self._circuit.record_success()
            return LLMCallResult(
                value=value,
                model=primary,
                degraded=False,
            )
        except LLMError as err:
            primary_error = err

        assert primary_error is not None

        # Permanent client errors (400/401): do not fallback.
        if not isinstance(primary_error, _TRANSIENT_ERRORS):
            self._circuit.record_failure()
            raise primary_error

        logger.warning(
            "llm_primary_exhausted",
            extra={
                "event": "llm_primary_exhausted",
                "model": primary,
                "error_type": type(primary_error).__name__,
                "fallback_model": fallback,
            },
        )

        if fallback and fallback != primary:
            try:
                value = await self._attempt(operation, fallback)
                self._circuit.record_success()
                logger.info(
                    "llm_fallback_success",
                    extra={
                        "event": "llm_fallback_success",
                        "model": fallback,
                    },
                )
                return LLMCallResult(
                    value=value,
                    model=fallback,
                    degraded=True,
                )
            except LLMError as fallback_error:
                self._circuit.record_failure()
                logger.error(
                    "llm_fallback_failed",
                    extra={
                        "event": "llm_fallback_failed",
                        "model": fallback,
                        "error_type": type(
                            fallback_error
                        ).__name__,
                    },
                )
                raise fallback_error

        self._circuit.record_failure()
        raise primary_error

    async def _retry_call(
        self,
        operation: InvokeFn[T],
        model: str,
    ) -> T:
        max_retries = self._settings.openai_max_retries
        last_error: LLMError | None = None

        for attempt in range(max_retries):
            try:
                return await self._attempt(operation, model)
            except LLMError as err:
                last_error = err
                if not isinstance(err, _TRANSIENT_ERRORS):
                    raise
                if attempt >= max_retries - 1:
                    break
                delay = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(
                    "llm_retry",
                    extra={
                        "event": "llm_retry",
                        "model": model,
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                        "delay_seconds": round(delay, 3),
                        "error_type": type(err).__name__,
                    },
                )
                await self._sleep(delay)

        assert last_error is not None
        raise last_error

    async def _attempt(
        self,
        operation: InvokeFn[T],
        model: str,
    ) -> T:
        timeout = self._settings.openai_timeout_seconds
        try:
            return await asyncio.wait_for(
                operation(model),
                timeout=timeout,
            )
        except LLMError:
            raise
        except Exception as exc:
            raise map_provider_error(exc) from exc


_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Process-wide client so the circuit breaker state is shared."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
