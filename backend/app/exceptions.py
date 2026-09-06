"""Typed failures for LLM calls and resilience controls."""


class LLMError(Exception):
    """Base error for any LLM client failure."""

    def __init__(
        self,
        message: str,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.cause = cause


class LLMTimeout(LLMError):
    """The LLM call exceeded the configured timeout."""


class LLMRateLimited(LLMError):
    """The provider rejected the call with HTTP 429."""


class LLMUnavailable(LLMError):
    """Transient provider failure (5xx) or exhausted retries."""


class CircuitOpen(LLMError):
    """Circuit breaker is open; the API must not be called."""
