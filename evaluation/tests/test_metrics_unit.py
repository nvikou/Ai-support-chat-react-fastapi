"""Unit tests for pure evaluation metrics."""

from __future__ import annotations

from evaluation.metrics.calibration import (
    expected_calibration_error,
    reliability_bins,
)
from evaluation.metrics.classification import binary_prf
from evaluation.metrics.generation import (
    groundedness_score,
    hallucination_rate,
    relevance_score,
)
from evaluation.metrics.performance import (
    estimate_batch_cost_usd,
    latency_percentiles,
)
def test_generation_proxies() -> None:
    answer = "refunds within 30 days"
    ctx = ["Refunds are available within 30 days of purchase."]
    assert groundedness_score(answer, ctx) > 0.5
    assert relevance_score(answer, "refunds within 30 days") == 1.0
    assert hallucination_rate("I do not know the answer", ctx) == 0.0


def test_escalation_f1() -> None:
    metrics = binary_prf(
        [True, True, False, False],
        [True, False, True, False],
    )
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5


def test_ece_and_bins() -> None:
    conf = [0.1, 0.2, 0.8, 0.9]
    correct = [False, False, True, True]
    ece = expected_calibration_error(conf, correct, n_bins=2)
    assert 0.0 <= ece <= 1.0
    bins = reliability_bins(conf, correct, n_bins=2)
    assert len(bins) == 2


def test_latency_and_cost() -> None:
    stats = latency_percentiles([0.1, 0.2, 0.3, 0.4])
    assert stats["p50"] == 0.25
    assert estimate_batch_cost_usd(per_request_usd=[0.01, 0.03]) == 20.0
