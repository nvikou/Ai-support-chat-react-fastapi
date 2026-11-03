"""Run the offline RAG evaluation harness and write reports.

Usage (from repo root)::

    python evaluation/run_eval.py
    python evaluation/run_eval.py --output evaluation/reports
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.dataset.constants import DATASET_VERSION  # noqa: E402
from evaluation.dataset.schema import validate_question_row  # noqa: E402
from evaluation.harness import (  # noqa: E402
    load_knowledge_store,
    predict_one,
)
from evaluation.metrics.calibration import (  # noqa: E402
    expected_calibration_error,
    reliability_bins,
)
from evaluation.metrics.classification import binary_prf  # noqa: E402
from evaluation.metrics.performance import (  # noqa: E402
    estimate_batch_cost_usd,
    latency_percentiles,
)
from evaluation.metrics.retrieval import aggregate_retrieval  # noqa: E402
from evaluation.reporting import (  # noqa: E402
    write_json_report,
    write_markdown_report,
    write_png_charts,
)

_LIMITS = (
    "Offline extractive stand-in (token-overlap retrieval + no live "
    "LLM). Generation scores are proxies, not judge-model grades. "
    "Synthetic NimbusDesk corpus; figures are not production SLAs."
)


def _load_questions(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        validate_question_row(row)
        rows.append(row)
    return rows


def run_evaluation(
    *,
    dataset_dir: Path,
    model: str = "gpt-4o-mini",
    k: int = 5,
) -> dict[str, Any]:
    """Evaluate all labeled questions; return report payload."""
    store = load_knowledge_store(dataset_dir / "knowledge")
    questions = _load_questions(dataset_dir / "questions.jsonl")
    version = (dataset_dir / "VERSION").read_text(encoding="utf-8").strip()
    if not version:
        version = DATASET_VERSION

    retrieval_rows: list[tuple[set[str], list[str]]] = []
    y_true: list[bool] = []
    y_pred: list[bool] = []
    grounded: list[float] = []
    relevance: list[float] = []
    halluc: list[float] = []
    confidences: list[float] = []
    correct_flags: list[bool] = []
    latencies: list[float] = []
    costs: list[float] = []

    for row in questions:
        pred = predict_one(
            question_id=str(row["id"]),
            question=str(row["question"]),
            expected_answer=str(row["expected_answer"]),
            expected_sources=list(row["expected_sources"]),
            should_escalate_label=bool(row["should_escalate"]),
            store=store,
            k=k,
            model=model,
        )
        gold = set(row["expected_sources"])
        retrieval_rows.append((gold, pred.ranked_doc_ids))
        y_true.append(bool(row["should_escalate"]))
        y_pred.append(pred.should_escalate)
        grounded.append(pred.groundedness)
        relevance.append(pred.relevance)
        halluc.append(pred.hallucination)
        confidences.append(pred.confidence)
        correct_flags.append(pred.correct)
        latencies.append(pred.latency_seconds)
        costs.append(pred.cost_usd)

    n = float(len(questions)) or 1.0
    bins = reliability_bins(confidences, correct_flags, n_bins=10)
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_version": version,
        "model": model,
        "mode": "offline-extractive",
        "question_count": len(questions),
        "retrieval": aggregate_retrieval(retrieval_rows, ks=(1, 3, 5)),
        "generation": {
            "groundedness": sum(grounded) / n,
            "relevance": sum(relevance) / n,
            "hallucination_rate": sum(halluc) / n,
        },
        "escalation": binary_prf(y_true, y_pred),
        "calibration": {
            "ece": expected_calibration_error(
                confidences,
                correct_flags,
                n_bins=10,
            ),
            "reliability_bins": [
                {
                    "lower": b.lower,
                    "upper": b.upper,
                    "count": b.count,
                    "avg_confidence": b.avg_confidence,
                    "accuracy": b.accuracy,
                }
                for b in bins
            ],
        },
        "performance": {
            **latency_percentiles(latencies),
            "cost_per_1000_usd": estimate_batch_cost_usd(
                per_request_usd=costs,
                scale_to=1000,
            ),
        },
        "limits": _LIMITS,
        "recall_at_5_threshold": 0.35,
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "evaluation" / "dataset",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evaluation" / "reports",
    )
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    payload = run_evaluation(
        dataset_dir=args.dataset,
        model=args.model,
        k=args.k,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_json_report(args.output / "report.json", payload)
    write_markdown_report(args.output / "report.md", payload)
    charts = write_png_charts(args.output, payload)
    payload["charts"] = charts
    write_json_report(args.output / "report.json", payload)

    recall5 = float(payload["retrieval"].get("recall@5", 0.0))
    threshold = float(payload["recall_at_5_threshold"])
    print(
        f"dataset={payload['dataset_version']} "
        f"recall@5={recall5:.4f} "
        f"ece={payload['calibration']['ece']:.4f} "
        f"charts={charts}"
    )
    if recall5 < threshold:
        raise SystemExit(f"recall@5 {recall5:.4f} below threshold {threshold:.4f}")


if __name__ == "__main__":
    main()
