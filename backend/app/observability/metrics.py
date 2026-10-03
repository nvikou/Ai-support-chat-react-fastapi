"""Prometheus metrics for LLM, RAG, and escalation signals.

Metrics live on an isolated ``CollectorRegistry`` so tests can reset
state without touching the process-wide default registry.
"""

from __future__ import annotations

import time
from typing import Any

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from app.observability.pricing import estimate_cost_usd

METRICS_CONTENT_TYPE = CONTENT_TYPE_LATEST

_LLM_DURATION_BUCKETS = (
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
)
_RAG_DURATION_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
)
_CONFIDENCE_BUCKETS = (
    0.1,
    0.2,
    0.3,
    0.4,
    0.5,
    0.6,
    0.7,
    0.8,
    0.9,
    1.0,
)


class AppMetrics:
    """Named collectors used by the API process."""

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry()
        self.llm_request_duration_seconds = Histogram(
            "llm_request_duration_seconds",
            "Wall time of resilient LLM invoke calls",
            labelnames=("model", "status"),
            buckets=_LLM_DURATION_BUCKETS,
            registry=self.registry,
        )
        self.llm_tokens_total = Counter(
            "llm_tokens_total",
            "Tokens reported by the provider",
            labelnames=("model", "type"),
            registry=self.registry,
        )
        self.llm_cost_usd_total = Counter(
            "llm_cost_usd_total",
            "Estimated USD spend from token usage",
            labelnames=("model",),
            registry=self.registry,
        )
        self.rag_retrieval_duration_seconds = Histogram(
            "rag_retrieval_duration_seconds",
            "Wall time of vector retrieval for an answer",
            buckets=_RAG_DURATION_BUCKETS,
            registry=self.registry,
        )
        self.rag_confidence_score = Histogram(
            "rag_confidence_score",
            "Composite confidence score distribution",
            buckets=_CONFIDENCE_BUCKETS,
            registry=self.registry,
        )
        self.conversations_escalated_total = Counter(
            "conversations_escalated_total",
            "Answers that triggered human escalation",
            labelnames=("reason",),
            registry=self.registry,
        )
        self.llm_errors_total = Counter(
            "llm_errors_total",
            "LLM failures by typed error class",
            labelnames=("error_type",),
            registry=self.registry,
        )
        self.circuit_breaker_state = Gauge(
            "circuit_breaker_state",
            "LLM circuit breaker (1=open, 0=closed)",
            registry=self.registry,
        )

    def observe_llm_request(
        self,
        *,
        model: str,
        status: str,
        duration_seconds: float,
    ) -> None:
        self.llm_request_duration_seconds.labels(
            model=model,
            status=status,
        ).observe(duration_seconds)

    def observe_llm_error(self, error_type: str) -> None:
        self.llm_errors_total.labels(error_type=error_type).inc()

    def set_circuit_state(self, *, is_open: bool) -> None:
        self.circuit_breaker_state.set(1.0 if is_open else 0.0)

    def observe_tokens(
        self,
        *,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        if prompt_tokens > 0:
            self.llm_tokens_total.labels(
                model=model,
                type="prompt",
            ).inc(prompt_tokens)
        if completion_tokens > 0:
            self.llm_tokens_total.labels(
                model=model,
                type="completion",
            ).inc(completion_tokens)
        if prompt_tokens > 0 or completion_tokens > 0:
            cost = estimate_cost_usd(
                model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            self.llm_cost_usd_total.labels(model=model).inc(cost)

    def observe_retrieval(self, duration_seconds: float) -> None:
        self.rag_retrieval_duration_seconds.observe(duration_seconds)

    def observe_confidence(self, score: float) -> None:
        clamped = max(0.0, min(1.0, score))
        self.rag_confidence_score.observe(clamped)

    def observe_escalation(self, reason: str) -> None:
        self.conversations_escalated_total.labels(
            reason=reason,
        ).inc()


_metrics: AppMetrics | None = None


def get_metrics() -> AppMetrics:
    global _metrics
    if _metrics is None:
        _metrics = AppMetrics()
    return _metrics


def reset_metrics_for_tests() -> None:
    """Test helper — do not call from production code."""
    global _metrics
    _metrics = AppMetrics()


def render_metrics() -> bytes:
    """Prometheus text exposition for ``GET /metrics``."""
    return generate_latest(get_metrics().registry)


def extract_token_usage(response: Any) -> tuple[int, int]:
    """Best-effort prompt/completion tokens from a LangChain message."""
    usage_meta = getattr(response, "usage_metadata", None)
    if isinstance(usage_meta, dict):
        prompt = _as_int(
            usage_meta.get("input_tokens") or usage_meta.get("prompt_tokens")
        )
        completion = _as_int(
            usage_meta.get("output_tokens")
            or usage_meta.get("completion_tokens")
        )
        if prompt or completion:
            return prompt, completion

    response_meta = getattr(response, "response_metadata", None)
    if isinstance(response_meta, dict):
        usage = (
            response_meta.get("token_usage")
            or response_meta.get("usage")
            or {}
        )
        if isinstance(usage, dict):
            prompt = _as_int(
                usage.get("prompt_tokens") or usage.get("input_tokens")
            )
            completion = _as_int(
                usage.get("completion_tokens") or usage.get("output_tokens")
            )
            return prompt, completion
    return 0, 0


def classify_escalation_reason(
    *,
    llm_unavailable: bool = False,
    degraded: bool = False,
    pattern_matched: bool = False,
) -> str:
    """Coarse label — never free-text (cardinality explosion)."""
    if llm_unavailable:
        return "llm_unavailable"
    if degraded:
        return "degraded"
    if pattern_matched:
        return "pattern"
    return "low_confidence"


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class Timer:
    """Monotonic duration helper for sync/async call sites."""

    def __init__(self) -> None:
        self._start = time.monotonic()

    def seconds(self) -> float:
        return time.monotonic() - self._start
