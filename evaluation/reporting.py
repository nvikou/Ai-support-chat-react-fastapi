"""Write evaluation reports: JSON, Markdown, and PNG charts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_markdown_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    retrieval = payload.get("retrieval", {})
    generation = payload.get("generation", {})
    escalation = payload.get("escalation", {})
    calibration = payload.get("calibration", {})
    performance = payload.get("performance", {})
    lines = [
        "# Evaluation report",
        "",
        f"- Dataset: `{payload.get('dataset_version', '?')}`",
        f"- Model (cost estimate): `{payload.get('model', '?')}`",
        f"- Mode: `{payload.get('mode', 'offline-extractive')}`",
        f"- Questions: **{payload.get('question_count', 0)}**",
        "",
        "## Retrieval",
        "",
        "| Metric | Value |",
        "|--------|------:|",
    ]
    for key in (
        "recall@1",
        "recall@3",
        "recall@5",
        "precision@1",
        "precision@3",
        "precision@5",
        "mrr",
    ):
        lines.append(f"| {key} | {retrieval.get(key, 0):.4f} |")
    lines.extend(
        [
            "",
            "## Generation (offline proxies)",
            "",
            "| Metric | Value |",
            "|--------|------:|",
            f"| groundedness | {generation.get('groundedness', 0):.4f} |",
            f"| relevance | {generation.get('relevance', 0):.4f} |",
            f"| hallucination_rate | "
            f"{generation.get('hallucination_rate', 0):.4f} |",
            "",
            "## Escalation",
            "",
            "| Metric | Value |",
            "|--------|------:|",
            f"| precision | {escalation.get('precision', 0):.4f} |",
            f"| recall | {escalation.get('recall', 0):.4f} |",
            f"| f1 | {escalation.get('f1', 0):.4f} |",
            "",
            "## Calibration",
            "",
            f"- ECE: **{calibration.get('ece', 0):.4f}**",
            "",
            "## Performance",
            "",
            "| Metric | Value |",
            "|--------|------:|",
            f"| latency mean (s) | {performance.get('mean', 0):.6f} |",
            f"| latency p50 (s) | {performance.get('p50', 0):.6f} |",
            f"| latency p95 (s) | {performance.get('p95', 0):.6f} |",
            f"| latency p99 (s) | {performance.get('p99', 0):.6f} |",
            f"| cost / 1000 req (USD) | "
            f"{performance.get('cost_per_1000_usd', 0):.4f} |",
            "",
            "## Limits",
            "",
            str(payload.get("limits", "")).strip(),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_png_charts(
    output_dir: Path,
    payload: dict[str, Any],
) -> list[str]:
    """Write reliability + retrieval bar charts; return filenames."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    try:
        bins = payload.get("calibration", {}).get("reliability_bins", [])
        if bins:
            centers = [
                (b["lower"] + b["upper"]) / 2.0 for b in bins if b.get("count", 0)
            ]
            acc = [b["accuracy"] for b in bins if b.get("count", 0)]
            conf = [b["avg_confidence"] for b in bins if b.get("count", 0)]
            fig, ax = plt.subplots(figsize=(6, 5))
            # Avoid ax.legend() — some matplotlib+Py3.14 builds recurse.
            ax.plot([0, 1], [0, 1], "k--")
            if centers:
                ax.bar(centers, acc, width=0.08, alpha=0.6, color="#93c5fd")
                ax.plot(centers, conf, "o-", color="#1d4ed8")
            ax.set_xlabel("Confidence")
            ax.set_ylabel("Accuracy")
            ax.set_title("Reliability (bars=accuracy, line=avg confidence)")
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            fig.tight_layout()
            path = output_dir / "reliability.png"
            fig.savefig(path, dpi=120)
            plt.close(fig)
            written.append(path.name)

        retrieval = payload.get("retrieval", {})
        labels = ["recall@1", "recall@3", "recall@5", "mrr"]
        values = [float(retrieval.get(key, 0.0)) for key in labels]
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(labels, values, color="#2563eb")
        ax.set_ylim(0, 1)
        ax.set_ylabel("Score")
        ax.set_title("Retrieval metrics")
        fig.tight_layout()
        path = output_dir / "retrieval.png"
        fig.savefig(path, dpi=120)
        plt.close(fig)
        written.append(path.name)
    except Exception:
        # Charts are optional; never fail the quality gate on plotting.
        for fig_num in list(getattr(plt, "get_fignums", lambda: [])()):
            plt.close(fig_num)
        return written

    return written
