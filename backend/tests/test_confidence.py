"""Tests for composite confidence scoring and related wiring."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.services.confidence import compute_confidence
from app.services.confidence import distance_to_similarity
from app.services.confidence import safe_compute_confidence
from app.services.escalation import load_escalation_patterns
from app.services.escalation import match_escalation
from app.services.groundedness import GroundednessCache
from app.services.groundedness import parse_groundedness_json
from app.services.prompts import build_system_prompt

def _score(**kwargs):
    defaults = {
        "retrieval_scores": [0.9, 0.4],
        "groundedness": 0.9,
        "answer_length": 120,
        "has_sources": True,
        "retrieval_min_similarity": 0.35,
        "escalation_threshold": 0.5,
        "uncertainty_threshold": 0.7,
    }
    defaults.update(kwargs)
    return compute_confidence(**defaults)


# --- retrieval_score signal ---


def test_retrieval_empty_scores_are_zero_signal() -> None:
    result = _score(retrieval_scores=[])
    assert result.signals["retrieval_score"] == 0.0


def test_retrieval_strong_gap_beats_weak_gap() -> None:
    strong = _score(retrieval_scores=[0.9, 0.2])
    weak = _score(retrieval_scores=[0.9, 0.88])
    assert (
        strong.signals["retrieval_score"]
        > weak.signals["retrieval_score"]
    )


def test_retrieval_best_hit_dominates_when_alone() -> None:
    result = _score(retrieval_scores=[0.8])
    assert result.signals["retrieval_score"] > 0.5


# --- groundedness signal ---


def test_groundedness_high_raises_composite() -> None:
    high = _score(groundedness=1.0)
    low = _score(groundedness=0.0)
    assert high.score > low.score
    assert high.signals["groundedness"] == 1.0
    assert low.signals["groundedness"] == 0.0


def test_groundedness_out_of_range_raises() -> None:
    with pytest.raises(ValueError, match="groundedness"):
        _score(groundedness=1.5)


# --- answer_length signal ---


def test_answer_length_zero_is_lowest() -> None:
    empty = _score(answer_length=0)
    mid = _score(answer_length=120)
    assert empty.signals["answer_length"] == 0.0
    assert mid.signals["answer_length"] == 1.0
    assert empty.score < mid.score


def test_answer_length_short_is_partial() -> None:
    result = _score(answer_length=20)
    assert 0.0 < result.signals["answer_length"] < 1.0


def test_answer_length_huge_is_penalized() -> None:
    mid = _score(answer_length=200)
    huge = _score(answer_length=5000)
    assert (
        huge.signals["answer_length"]
        < mid.signals["answer_length"]
    )


# --- sources signal ---


def test_missing_sources_lowers_score() -> None:
    with_src = _score(has_sources=True)
    without = _score(has_sources=False)
    assert with_src.signals["sources"] == 1.0
    assert without.signals["sources"] == 0.0
    assert with_src.score > without.score


# --- no_context_penalty ---


def test_no_context_caps_score_at_0_3() -> None:
    result = _score(
        retrieval_scores=[0.1, 0.05],
        groundedness=1.0,
        answer_length=200,
        has_sources=True,
        retrieval_min_similarity=0.35,
    )
    assert result.signals["no_context_penalty"] == 1.0
    assert result.score == pytest.approx(0.3)
    assert "capped" in result.reason.lower()


def test_context_above_floor_not_capped() -> None:
    result = _score(
        retrieval_scores=[0.9, 0.3],
        groundedness=1.0,
        retrieval_min_similarity=0.35,
    )
    assert result.signals["no_context_penalty"] == 0.0
    assert result.score > 0.3


# --- bounds & bands ---


def test_score_never_below_zero() -> None:
    result = _score(
        retrieval_scores=[],
        groundedness=0.0,
        answer_length=0,
        has_sources=False,
    )
    assert result.score == 0.0
    assert result.band == "low"


def test_score_never_above_one() -> None:
    result = _score(
        retrieval_scores=[1.0, 0.0],
        groundedness=1.0,
        answer_length=150,
        has_sources=True,
    )
    assert result.score <= 1.0
    assert result.score == pytest.approx(1.0, abs=0.05)


def test_bands_follow_configured_thresholds() -> None:
    low = _score(
        retrieval_scores=[0.2],
        groundedness=0.1,
        answer_length=10,
        has_sources=False,
        escalation_threshold=0.5,
        uncertainty_threshold=0.7,
    )
    medium = _score(
        retrieval_scores=[0.55, 0.5],
        groundedness=0.55,
        answer_length=120,
        has_sources=True,
        escalation_threshold=0.5,
        uncertainty_threshold=0.7,
    )
    high = _score(
        retrieval_scores=[0.95, 0.2],
        groundedness=1.0,
        answer_length=120,
        has_sources=True,
        escalation_threshold=0.5,
        uncertainty_threshold=0.7,
    )
    assert low.band == "low"
    assert medium.band == "medium"
    assert high.band == "high"


def test_inverted_thresholds_raise() -> None:
    with pytest.raises(ValueError, match="uncertainty_threshold"):
        _score(
            escalation_threshold=0.8,
            uncertainty_threshold=0.5,
        )


# --- fail closed ---


def test_fail_closed_returns_zero_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        result = safe_compute_confidence(
            retrieval_scores=[0.9],
            groundedness=99.0,
            answer_length=10,
            has_sources=True,
        )
    assert result.score == 0.0
    assert result.band == "low"
    assert "fail" in result.reason.lower()
    assert any(
        "confidence_fail_closed" in r.message
        or r.__dict__.get("event") == "confidence_fail_closed"
        for r in caplog.records
    ) or any(
        "fail" in r.getMessage().lower() for r in caplog.records
    )


# --- config ↔ prompt coherence ---


def test_prompt_interpolates_uncertainty_threshold() -> None:
    prompt = build_system_prompt(uncertainty_threshold=0.7)
    assert "0.7" in prompt
    assert "CONFIDENCE:" not in prompt


def test_prompt_tracks_settings_threshold() -> None:
    from app.config import Settings

    # Settings field used by agent must match prompt interpolation.
    field = Settings.model_fields[
        "confidence_uncertainty_threshold"
    ]
    default = field.default
    prompt = build_system_prompt(
        uncertainty_threshold=float(default),
    )
    assert str(default) in prompt
    escal = Settings.model_fields[
        "confidence_escalation_threshold"
    ].default
    assert float(default) >= float(escal)


def test_distance_to_similarity_bounds() -> None:
    assert distance_to_similarity(0.0) == 1.0
    assert 0.0 < distance_to_similarity(1.0) < 1.0
    assert distance_to_similarity(100.0) < distance_to_similarity(
        1.0
    )


# --- groundedness parse / cache (no network) ---


def test_parse_groundedness_json_strict() -> None:
    assert parse_groundedness_json(
        '{"groundedness": 0.75, "supported": 3, "total": 4}'
    ) == 0.75
    with pytest.raises((ValueError, KeyError, TypeError)):
        parse_groundedness_json("not-json")


def test_groundedness_cache_by_hashes() -> None:
    cache = GroundednessCache()
    cache.set("q", "a", 0.8)
    assert cache.get("q", "a") == 0.8
    assert cache.get("q", "other") is None


# --- escalation patterns ---


def test_escalation_pattern_reports_category() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "data"
        / "escalation_patterns.yaml"
    )
    patterns = load_escalation_patterns(path)
    match = match_escalation("I want a refund now", patterns)
    assert match is not None
    assert match.category == "financial"
    assert "financial" in match.reason


def test_escalation_french_explicit_request() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "data"
        / "escalation_patterns.yaml"
    )
    patterns = load_escalation_patterns(path)
    match = match_escalation(
        "Je veux parler à un humain",
        patterns,
    )
    assert match is not None
    assert match.language == "fr"
    assert match.category == "explicit_request"
