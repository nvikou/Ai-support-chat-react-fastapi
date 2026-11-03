"""Smoke test for the offline evaluation harness."""

from __future__ import annotations

from pathlib import Path

from evaluation.run_eval import run_evaluation

DATASET = Path(__file__).resolve().parents[1] / "dataset"


def test_run_evaluation_smoke() -> None:
    payload = run_evaluation(dataset_dir=DATASET, model="gpt-4o-mini")
    assert payload["question_count"] == 180
    assert "recall@5" in payload["retrieval"]
    assert "ece" in payload["calibration"]
    assert "cost_per_1000_usd" in payload["performance"]
    assert payload["retrieval"]["recall@5"] >= 0.0
