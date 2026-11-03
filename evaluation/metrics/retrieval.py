"""Information-retrieval metrics over ranked doc_id lists."""

from __future__ import annotations


def recall_at_k(
    relevant: set[str],
    ranked: list[str],
    *,
    k: int,
) -> float:
    """Fraction of gold sources found in the top-``k`` hits."""
    if not relevant:
        # No gold sources (OOD/unknown): perfect iff nothing retrieved
        # that claims relevance — treat empty gold as recall 1.0 when
        # ranked[:k] is also empty, else 0.0.
        return 1.0 if not ranked[:k] else 0.0
    if k <= 0:
        return 0.0
    hit = relevant.intersection(ranked[:k])
    return len(hit) / len(relevant)


def precision_at_k(
    relevant: set[str],
    ranked: list[str],
    *,
    k: int,
) -> float:
    """Fraction of top-``k`` hits that are gold sources."""
    if k <= 0:
        return 0.0
    top = ranked[:k]
    if not top:
        return 0.0 if relevant else 1.0
    hit = relevant.intersection(top)
    return len(hit) / len(top)


def mean_reciprocal_rank(
    relevant: set[str],
    ranked: list[str],
) -> float:
    """Reciprocal rank of the first gold hit (0 if none)."""
    if not relevant:
        return 1.0 if not ranked else 0.0
    for index, doc_id in enumerate(ranked, start=1):
        if doc_id in relevant:
            return 1.0 / index
    return 0.0


def aggregate_retrieval(
    rows: list[tuple[set[str], list[str]]],
    *,
    ks: tuple[int, ...] = (1, 3, 5),
) -> dict[str, float]:
    """Mean recall@k / precision@k / MRR across labeled rows."""
    if not rows:
        return (
            {f"recall@{k}": 0.0 for k in ks}
            | {f"precision@{k}": 0.0 for k in ks}
            | {"mrr": 0.0}
        )
    n = float(len(rows))
    out: dict[str, float] = {}
    for k in ks:
        out[f"recall@{k}"] = (
            sum(recall_at_k(rel, ranked, k=k) for rel, ranked in rows) / n
        )
        out[f"precision@{k}"] = (
            sum(precision_at_k(rel, ranked, k=k) for rel, ranked in rows) / n
        )
    out["mrr"] = sum(mean_reciprocal_rank(rel, ranked) for rel, ranked in rows) / n
    return out
