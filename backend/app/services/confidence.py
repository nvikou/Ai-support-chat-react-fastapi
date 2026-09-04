"""Composite confidence from measurable retrieval signals.

Pure scoring only: callers supply numbers; this module never
talks to the network or the filesystem.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

Band = Literal["high", "medium", "low"]

# Soft length band (chars). Outside it, answers look thin or rambling.
_LENGTH_SHORT = 40
_LENGTH_LONG = 2000
# Gap (best - second) at which retrieval looks discriminative.
_GAP_FULL_CREDIT = 0.15

_NO_CONTEXT_CAP = 0.3


@dataclass(frozen=True)
class ConfidenceResult:
    """Scored confidence plus the signals that produced it."""

    score: float
    band: Band
    signals: dict[str, float]
    reason: str


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def distance_to_similarity(distance: float) -> float:
    """Convert FAISS L2 distance into a bounded similarity in (0, 1].

    Why: FAISS returns distances (lower is closer). Confidence math
    needs a similarity where higher means a stronger retrieval hit.
    """
    return 1.0 / (1.0 + max(0.0, float(distance)))


def _retrieval_signal(retrieval_scores: list[float]) -> float:
    """Best-hit strength plus 1st/2nd gap.

    Why: a strong top hit that clearly beats the runner-up means the
    index found a distinctive match; a tiny gap means several chunks
    look equally plausible, so the base cannot discriminate.
    """
    if not retrieval_scores:
        return 0.0
    ordered = sorted(
        (_clamp(float(s)) for s in retrieval_scores),
        reverse=True,
    )
    best = ordered[0]
    second = ordered[1] if len(ordered) > 1 else 0.0
    gap = max(0.0, best - second)
    gap_factor = _clamp(gap / _GAP_FULL_CREDIT)
    return _clamp(0.65 * best + 0.35 * gap_factor)


def _length_signal(answer_length: int) -> float:
    """Prefer answers long enough to be useful but not sprawling.

    Why: tiny replies often dodge the question; extremely long ones
    tend to pad when evidence is weak. Mid-range length correlates
    with a concrete, supportable answer.
    """
    if answer_length <= 0:
        return 0.0
    if answer_length < _LENGTH_SHORT:
        return _clamp(answer_length / _LENGTH_SHORT)
    if answer_length > _LENGTH_LONG:
        overflow = answer_length - _LENGTH_LONG
        return _clamp(1.0 - overflow / _LENGTH_LONG)
    return 1.0


def _sources_signal(has_sources: bool) -> float:
    """Binary presence of cited retrieval sources.

    Why: an answer with no attributable sources cannot be checked
    against the knowledge base, so we treat that as low trust.
    """
    return 1.0 if has_sources else 0.0


def _band_for(
    score: float,
    *,
    escalation_threshold: float,
    uncertainty_threshold: float,
) -> Band:
    if score >= uncertainty_threshold:
        return "high"
    if score >= escalation_threshold:
        return "medium"
    return "low"


def compute_confidence(
    retrieval_scores: list[float],
    groundedness: float,
    answer_length: int,
    has_sources: bool,
    *,
    retrieval_min_similarity: float = 0.35,
    escalation_threshold: float = 0.5,
    uncertainty_threshold: float = 0.7,
) -> ConfidenceResult:
    """Combine measurable signals into a calibrated confidence score.

    Signals
    -------
    retrieval_score
        Best similarity plus 1st-vs-2nd gap. A weak gap means the
        knowledge base does not discriminate, so certainty should fall.
    groundedness
        Share of answer claims supported by retrieved docs. High
        groundedness means the reply is tethered to evidence, not
        invented. (Computed upstream; this function only consumes it.)
    answer_length
        Length as a soft quality prior: empty/tiny or huge answers
        are less trustworthy than mid-range ones.
    sources
        Whether any source documents were attached. No sources means
        the answer cannot be audited against the corpus.
    no_context_penalty
        If no retrieved hit clears ``retrieval_min_similarity``, the
        final score is capped at 0.3 — we refuse to look confident
        without usable context.
    """
    if uncertainty_threshold < escalation_threshold:
        raise ValueError(
            "uncertainty_threshold must be >= escalation_threshold"
        )
    if not 0.0 <= groundedness <= 1.0:
        raise ValueError("groundedness must be in [0.0, 1.0]")
    if answer_length < 0:
        raise ValueError("answer_length must be >= 0")

    retrieval = _retrieval_signal(retrieval_scores)
    grounded = _clamp(float(groundedness))
    length = _length_signal(answer_length)
    sources = _sources_signal(has_sources)

    # Weighted blend — retrieval + groundedness dominate.
    raw = (
        0.40 * retrieval
        + 0.40 * grounded
        + 0.10 * length
        + 0.10 * sources
    )
    raw = _clamp(raw)

    best_hit = (
        max(float(s) for s in retrieval_scores)
        if retrieval_scores
        else 0.0
    )
    no_context = best_hit < retrieval_min_similarity
    score = min(raw, _NO_CONTEXT_CAP) if no_context else raw
    score = _clamp(score)

    signals = {
        "retrieval_score": retrieval,
        "groundedness": grounded,
        "answer_length": length,
        "sources": sources,
        "no_context_penalty": 1.0 if no_context else 0.0,
        "best_hit": _clamp(best_hit),
    }

    band = _band_for(
        score,
        escalation_threshold=escalation_threshold,
        uncertainty_threshold=uncertainty_threshold,
    )

    if no_context:
        reason = (
            "No retrieval hit cleared the similarity floor; "
            f"score capped at {_NO_CONTEXT_CAP:.1f}"
        )
    elif band == "low":
        reason = (
            f"Composite confidence {score:.2f} is below "
            f"escalation threshold {escalation_threshold:.2f}"
        )
    elif band == "medium":
        reason = (
            f"Composite confidence {score:.2f} is below "
            f"uncertainty threshold {uncertainty_threshold:.2f}"
        )
    else:
        reason = (
            f"Composite confidence {score:.2f} clears "
            f"uncertainty threshold {uncertainty_threshold:.2f}"
        )

    return ConfidenceResult(
        score=score,
        band=band,
        signals=signals,
        reason=reason,
    )


def safe_compute_confidence(
    *args,
    **kwargs,
) -> ConfidenceResult:
    """Fail closed: any scoring error yields 0.0 and forces caution."""
    try:
        return compute_confidence(*args, **kwargs)
    except Exception as exc:
        logger.warning(
            "confidence_fail_closed",
            extra={
                "event": "confidence_fail_closed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        return ConfidenceResult(
            score=0.0,
            band="low",
            signals={},
            reason=(
                "Confidence computation failed — "
                "failing closed to force escalation"
            ),
        )
