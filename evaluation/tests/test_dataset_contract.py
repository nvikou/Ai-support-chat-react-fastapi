"""Contract tests for the seeded evaluation dataset."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from evaluation.dataset.constants import (
    DATASET_SEED,
    DATASET_VERSION,
    MAX_DOCS,
    MAX_QUESTIONS,
    MIN_DOCS,
    MIN_QUESTIONS,
    TARGET_DOCS,
    TARGET_QUESTIONS,
)
from evaluation.dataset.knowledge import build_knowledge_docs
from evaluation.dataset.questions import build_labeled_questions
from evaluation.dataset.schema import ALLOWED_CATEGORIES, validate_question_row
from evaluation.scripts.generate_dataset import generate

DATASET_DIR = Path(__file__).resolve().parents[1] / "dataset"
HARD_CATEGORIES = frozenset(
    {
        "multi_source",
        "out_of_scope",
        "unknown",
        "ambiguous",
        "prompt_injection",
    }
)


def test_knowledge_size_band() -> None:
    docs = build_knowledge_docs()
    assert MIN_DOCS <= len(docs) <= MAX_DOCS
    assert len(docs) == TARGET_DOCS


def test_questions_size_and_schema() -> None:
    docs = build_knowledge_docs()
    questions = build_labeled_questions(docs, random.Random(DATASET_SEED))
    assert MIN_QUESTIONS <= len(questions) <= MAX_QUESTIONS
    assert len(questions) == TARGET_QUESTIONS
    for item in questions:
        row = item.to_json_row()
        validate_question_row(row)
        assert item.category in ALLOWED_CATEGORIES


def test_hard_categories_are_present() -> None:
    docs = build_knowledge_docs()
    questions = build_labeled_questions(docs, random.Random(DATASET_SEED))
    seen = {item.category for item in questions}
    missing = HARD_CATEGORIES - seen
    assert not missing, f"missing hard categories: {missing}"


def test_seed_is_deterministic() -> None:
    docs = build_knowledge_docs()
    a = [
        q.to_json_row()
        for q in build_labeled_questions(docs, random.Random(DATASET_SEED))
    ]
    b = [
        q.to_json_row()
        for q in build_labeled_questions(docs, random.Random(DATASET_SEED))
    ]
    assert a == b


def test_generate_writes_artifacts(tmp_path: Path) -> None:
    manifest = generate(tmp_path, DATASET_SEED)
    assert manifest["dataset_version"] == DATASET_VERSION
    assert (tmp_path / "VERSION").read_text(encoding="utf-8").strip() == (
        DATASET_VERSION
    )
    questions_path = tmp_path / "questions.jsonl"
    assert questions_path.is_file()
    rows = [
        json.loads(line)
        for line in questions_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == TARGET_QUESTIONS
    knowledge = list((tmp_path / "knowledge").glob("*.md"))
    assert len(knowledge) == TARGET_DOCS


@pytest.mark.skipif(
    not (DATASET_DIR / "questions.jsonl").is_file(),
    reason="committed artifacts not generated yet",
)
def test_committed_artifacts_match_generator(tmp_path: Path) -> None:
    """Pin CI to the checked-in dataset once materialised."""
    fresh = generate(tmp_path, DATASET_SEED)
    committed = json.loads((DATASET_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert committed["questions_sha256"] == fresh["questions_sha256"]
    assert committed["doc_count"] == fresh["doc_count"]
    assert committed["question_count"] == fresh["question_count"]
