"""Unit tests for retrieval IR helpers only."""

from __future__ import annotations

from evaluation.metrics.retrieval import (
    aggregate_retrieval,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
)


def test_recall_and_precision_at_k() -> None:
    relevant = {"a", "b"}
    ranked = ["a", "x", "b"]
    assert recall_at_k(relevant, ranked, k=1) == 0.5
    assert recall_at_k(relevant, ranked, k=3) == 1.0
    assert precision_at_k(relevant, ranked, k=2) == 0.5
    assert mean_reciprocal_rank(relevant, ranked) == 1.0


def test_aggregate_retrieval() -> None:
    rows = [
        ({"a"}, ["a", "b"]),
        ({"c"}, ["x", "c"]),
    ]
    out = aggregate_retrieval(rows, ks=(1, 2))
    assert out["recall@1"] == 0.5
    assert out["mrr"] == 0.75
