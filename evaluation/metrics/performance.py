"""Latency percentiles and cost extrapolation."""

from __future__ import annotations

import math


def latency_percentiles(
    seconds: list[float],
) -> dict[str, float]:
    """Return mean, p50, p95, p99 for observed latencies."""
    if not seconds:
        return {"mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
    ordered = sorted(seconds)
    return {
        "mean": sum(ordered) / len(ordered),
        "p50": _percentile(ordered, 50),
        "p95": _percentile(ordered, 95),
        "p99": _percentile(ordered, 99),
    }


def _percentile(ordered: list[float], pct: float) -> float:
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(math.floor(rank))
    high = int(math.ceil(rank))
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def estimate_batch_cost_usd(
    *,
    per_request_usd: list[float],
    scale_to: int = 1000,
) -> float:
    """Extrapolate mean per-request cost to ``scale_to`` requests."""
    if not per_request_usd:
        return 0.0
    mean = sum(per_request_usd) / len(per_request_usd)
    return mean * float(scale_to)
