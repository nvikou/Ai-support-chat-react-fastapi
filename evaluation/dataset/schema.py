"""Contracts for knowledge docs and labeled questions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


ALLOWED_CATEGORIES = frozenset(
    {
        "billing",
        "accounts",
        "api",
        "troubleshooting",
        "multi_source",
        "out_of_scope",
        "unknown",
        "ambiguous",
        "prompt_injection",
    }
)


@dataclass(frozen=True)
class KnowledgeDoc:
    """One retrievable knowledge-base document."""

    doc_id: str
    category: str
    title: str
    body: str

    def to_markdown(self) -> str:
        return (
            f"# {self.title}\n\n"
            f"<!-- doc_id: {self.doc_id} -->\n"
            f"<!-- category: {self.category} -->\n\n"
            f"{self.body.strip()}\n"
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LabeledQuestion:
    """One evaluation item with gold labels."""

    id: str
    question: str
    expected_answer: str
    expected_sources: tuple[str, ...]
    category: str
    should_escalate: bool
    difficulty: str = "standard"

    def to_json_row(self) -> dict[str, Any]:
        if self.category not in ALLOWED_CATEGORIES:
            raise ValueError(f"unknown category: {self.category}")
        return {
            "id": self.id,
            "question": self.question,
            "expected_answer": self.expected_answer,
            "expected_sources": list(self.expected_sources),
            "category": self.category,
            "should_escalate": self.should_escalate,
            "difficulty": self.difficulty,
        }


def validate_question_row(row: dict[str, Any]) -> None:
    """Raise ``ValueError`` if a JSONL row is malformed."""
    required = (
        "id",
        "question",
        "expected_answer",
        "expected_sources",
        "category",
        "should_escalate",
    )
    missing = [key for key in required if key not in row]
    if missing:
        raise ValueError(f"missing fields: {missing}")
    if not isinstance(row["question"], str) or not row["question"].strip():
        raise ValueError("question must be a non-empty string")
    if not isinstance(row["expected_answer"], str):
        raise ValueError("expected_answer must be a string")
    if not isinstance(row["expected_sources"], list):
        raise ValueError("expected_sources must be a list")
    if row["category"] not in ALLOWED_CATEGORIES:
        raise ValueError(f"bad category: {row['category']}")
    if not isinstance(row["should_escalate"], bool):
        raise ValueError("should_escalate must be a bool")
