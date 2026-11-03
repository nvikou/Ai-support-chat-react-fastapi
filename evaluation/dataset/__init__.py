"""Labeled RAG evaluation dataset (synthetic NimbusDesk KB)."""

from evaluation.dataset.constants import (
    DATASET_SEED,
    DATASET_VERSION,
    MAX_DOCS,
    MAX_QUESTIONS,
    MIN_DOCS,
    MIN_QUESTIONS,
)
from evaluation.dataset.schema import KnowledgeDoc, LabeledQuestion

__all__ = [
    "DATASET_SEED",
    "DATASET_VERSION",
    "MAX_DOCS",
    "MAX_QUESTIONS",
    "MIN_DOCS",
    "MIN_QUESTIONS",
    "KnowledgeDoc",
    "LabeledQuestion",
]
