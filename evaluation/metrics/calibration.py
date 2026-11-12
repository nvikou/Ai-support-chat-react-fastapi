"""Confidence calibration: reliability bins and ECE."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReliabilityBin:
    """One equal-width confidence bucket."""

    lower: float
    upper: float
    count: int
    avg_confidence: float
    accuracy: float


def reliability_bins(
    confidences: list[float],
    correct: list[bool],
    *,
    n_bins: int = 10,
) -> list[ReliabilityBin]:
    """Equal-width bins on [0, 1] for a reliability diagram."""
    if len(confidences) != len(correct):
        raise ValueError("confidences and correct length mismatch")
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")
    bins: list[ReliabilityBin] = []
    for index in range(n_bins):
        lower = index / n_bins
        upper = (index + 1) / n_bins
        members: list[tuple[float, bool]] = []
        for conf, is_ok in zip(confidences, correct, strict=True):
            # Last bin is closed on the right.
            if index == n_bins - 1:
                if lower <= conf <= upper:
                    members.append((conf, is_ok))
            elif lower <= conf < upper:
                members.append((conf, is_ok))
        if not members:
            bins.append(
                ReliabilityBin(
                    lower=lower,
                    upper=upper,
                    count=0,
                    avg_confidence=0.0,
                    accuracy=0.0,
                )
            )
            continue
        avg_conf = sum(c for c, _ in members) / len(members)
        acc = sum(1 for _, ok in members if ok) / len(members)
        bins.append(
            ReliabilityBin(
                lower=lower,
                upper=upper,
                count=len(members),
                avg_confidence=avg_conf,
                accuracy=acc,
            )
        )
    return bins


def expected_calibration_error(
    confidences: list[float],
    correct: list[bool],
    *,
    n_bins: int = 10,
) -> float:
    """ECE = sum_b (|B_b|/n) * |acc(B_b) - conf(B_b)|."""
    if not confidences:
        return 0.0
    bins = reliability_bins(confidences, correct, n_bins=n_bins)
    total = float(len(confidences))
    ece = 0.0
    for bucket in bins:
        if bucket.count == 0:
            continue
        ece += (bucket.count / total) * abs(bucket.accuracy - bucket.avg_confidence)
    return ece
