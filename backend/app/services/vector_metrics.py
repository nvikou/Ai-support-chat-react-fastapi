"""In-process vector-store signals for ADR 0001 thresholds.

Not a replacement for Prometheus: these counters live in one API
process so operators can hit ``GET /admin/vector-store`` and see
pending backlog and approximate search QPS without new infra. When
replicas > 1, scrape each instance or move to Redis/Prometheus.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

# Mirrors docs/adr/0001-vector-store.md — keep in sync when changing ADR.
ADR_CHUNKS_WARN = 50_000
ADR_SEARCH_QPS_WARN = 20.0
ADR_PENDING_BACKLOG_WARN = 10


@dataclass(frozen=True)
class SearchMetrics:
    total: int
    qps_approx: float
    window_seconds: float


class VectorStoreMetrics:
    """Sliding-window search counter (monotonic clock)."""

    def __init__(self, window_seconds: float = 60.0) -> None:
        self._window = window_seconds
        self._lock = threading.Lock()
        self._total = 0
        self._events: deque[float] = deque()

    def record_search(self) -> None:
        now = time.monotonic()
        with self._lock:
            self._total += 1
            self._events.append(now)
            self._trim(now)

    def snapshot(self) -> SearchMetrics:
        now = time.monotonic()
        with self._lock:
            self._trim(now)
            count = len(self._events)
            qps = count / self._window if self._window > 0 else 0.0
            return SearchMetrics(
                total=self._total,
                qps_approx=round(qps, 3),
                window_seconds=self._window,
            )

    def _trim(self, now: float) -> None:
        cutoff = now - self._window
        while self._events and self._events[0] < cutoff:
            self._events.popleft()


_metrics: VectorStoreMetrics | None = None


def get_vector_metrics() -> VectorStoreMetrics:
    global _metrics
    if _metrics is None:
        _metrics = VectorStoreMetrics()
    return _metrics


def reset_vector_metrics_for_tests() -> None:
    """Test helper — do not call from production code."""
    global _metrics
    _metrics = VectorStoreMetrics()
