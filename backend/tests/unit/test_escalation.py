"""Unit tests for YAML escalation pattern matching."""

from __future__ import annotations

from app.services.escalation import match_escalation


_PATTERNS = {
    "en": {
        "legal": ["lawyer", "sue you"],
        "billing": ["chargeback"],
    },
    "fr": {
        "legal": ["avocat", "plainte"],
    },
}


def test_match_escalation_finds_english_legal() -> None:
    hit = match_escalation(
        "I will call my lawyer tomorrow",
        patterns=_PATTERNS,
    )
    assert hit is not None
    assert hit.language == "en"
    assert hit.category == "legal"
    assert hit.pattern == "lawyer"
    assert "Escalation pattern matched" in hit.reason


def test_match_escalation_is_case_insensitive() -> None:
    hit = match_escalation("CHARGEBACK now", patterns=_PATTERNS)
    assert hit is not None
    assert hit.category == "billing"


def test_match_escalation_supports_french() -> None:
    hit = match_escalation(
        "Je vais voir mon avocat",
        patterns=_PATTERNS,
    )
    assert hit is not None
    assert hit.language == "fr"


def test_match_escalation_returns_none_when_clean() -> None:
    assert (
        match_escalation(
            "How do I reset my password?",
            patterns=_PATTERNS,
        )
        is None
    )
