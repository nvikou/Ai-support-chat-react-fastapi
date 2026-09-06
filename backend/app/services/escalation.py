"""Load and match multilingual escalation patterns from YAML."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_PATTERNS_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "escalation_patterns.yaml"
)


@dataclass(frozen=True)
class EscalationMatch:
    """A pattern that fired for the customer message."""

    language: str
    category: str
    pattern: str

    @property
    def reason(self) -> str:
        return (
            f"Escalation pattern matched — category={self.category}, "
            f"lang={self.language}, pattern={self.pattern!r}"
        )


def load_escalation_patterns(
    path: Path | None = None,
) -> dict[str, Any]:
    """Load YAML patterns; ``path`` override supports tests."""
    target = path or _PATTERNS_PATH
    with target.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("escalation patterns root must be a mapping")
    return data


@lru_cache(maxsize=1)
def _cached_patterns() -> dict[str, Any]:
    return load_escalation_patterns()


def match_escalation(
    text: str,
    patterns: dict[str, Any] | None = None,
) -> EscalationMatch | None:
    """Return the first matching pattern, or None."""
    haystack = text.lower()
    data = patterns if patterns is not None else _cached_patterns()
    for language, categories in data.items():
        if not isinstance(categories, dict):
            continue
        for category, phrases in categories.items():
            if not phrases:
                continue
            for phrase in phrases:
                needle = str(phrase).lower().strip()
                if needle and needle in haystack:
                    return EscalationMatch(
                        language=str(language),
                        category=str(category),
                        pattern=str(phrase),
                    )
    return None
