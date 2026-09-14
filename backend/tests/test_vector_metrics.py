"""Tests for ADR-aligned in-process vector metrics."""

from __future__ import annotations

from app.services.vector_metrics import VectorStoreMetrics
from app.services.vector_metrics import reset_vector_metrics_for_tests


def test_search_qps_uses_sliding_window() -> None:
    metrics = VectorStoreMetrics(window_seconds=10.0)
    clock = {"now": 100.0}

    def fake_clock() -> float:
        return clock["now"]

    # Inject clock via recording with patched monotonic in method body:
    # call record/snapshot with controlled time by monkeypatching module.
    import app.services.vector_metrics as mod

    original = mod.time.monotonic
    mod.time.monotonic = fake_clock  # type: ignore[method-assign]
    try:
        metrics.record_search()
        clock["now"] = 101.0
        metrics.record_search()
        snap = metrics.snapshot()
        assert snap.total == 2
        assert snap.qps_approx == 0.2
        clock["now"] = 120.0
        snap_later = metrics.snapshot()
        assert snap_later.total == 2
        assert snap_later.qps_approx == 0.0
    finally:
        mod.time.monotonic = original  # type: ignore[method-assign]


def test_reset_helper_clears_singleton() -> None:
    reset_vector_metrics_for_tests()
    from app.services.vector_metrics import get_vector_metrics

    m = get_vector_metrics()
    m.record_search()
    assert m.snapshot().total == 1
    reset_vector_metrics_for_tests()
    assert get_vector_metrics().snapshot().total == 0
