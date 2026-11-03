"""Offline extractive RAG stand-in for evaluation (no OpenAI)."""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.observability.pricing import estimate_cost_usd  # noqa: E402
from app.services.confidence import safe_compute_confidence  # noqa: E402
from app.services.escalation import match_escalation  # noqa: E402
from app.services.vector_store import (  # noqa: E402
    InMemoryVectorStore,
    ScoredDocument,
)

from evaluation.metrics.generation import (  # noqa: E402
    groundedness_score,
    hallucination_rate,
    relevance_score,
)

_ABSTAIN = "I do not have enough knowledge-base context " "for that question."
_DOC_ID_RE = re.compile(r"<!--\s*doc_id:\s*([^\s]+)\s*-->")


@dataclass(frozen=True)
class EvalPrediction:
    """One offline prediction for a labeled question."""

    question_id: str
    ranked_doc_ids: list[str]
    retrieval_scores: list[float]
    answer: str
    groundedness: float
    relevance: float
    hallucination: float
    confidence: float
    should_escalate: bool
    latency_seconds: float
    cost_usd: float
    correct: bool


def load_knowledge_store(knowledge_dir: Path) -> InMemoryVectorStore:
    """Index markdown docs; ``metadata.doc_id`` from HTML comment."""
    store = InMemoryVectorStore()
    documents: list[dict[str, Any]] = []
    for path in sorted(knowledge_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        match = _DOC_ID_RE.search(text)
        doc_id = match.group(1) if match else path.stem
        documents.append(
            {
                "content": text,
                "metadata": {"doc_id": doc_id, "source": doc_id},
            }
        )
    store.add_documents(documents)
    return store


def _ranked_ids(
    hits: list[ScoredDocument],
    *,
    min_score: float = 0.05,
) -> tuple[list[str], list[float]]:
    ids: list[str] = []
    scores: list[float] = []
    for hit in hits:
        if hit.score < min_score:
            continue
        doc_id = str(hit.metadata.get("doc_id") or "")
        if not doc_id:
            continue
        ids.append(doc_id)
        scores.append(float(hit.score))
    return ids, scores


def _extractive_answer(
    hits: list[ScoredDocument],
    *,
    min_score: float,
) -> str:
    if not hits or hits[0].score < min_score:
        return _ABSTAIN
    # Prefer body without markdown chrome for overlap metrics.
    body = hits[0].content
    lines = [
        line
        for line in body.splitlines()
        if line.strip()
        and not line.strip().startswith("<!--")
        and not line.strip().startswith("#")
    ]
    return " ".join(lines) if lines else _ABSTAIN


def predict_one(
    *,
    question_id: str,
    question: str,
    expected_answer: str,
    expected_sources: list[str],
    should_escalate_label: bool,
    store: InMemoryVectorStore,
    k: int = 5,
    retrieval_min_similarity: float = 0.35,
    escalation_threshold: float = 0.5,
    model: str = "gpt-4o-mini",
) -> EvalPrediction:
    """Retrieve + extractive answer + confidence/escalation offline."""
    del should_escalate_label  # label used by caller metrics only
    started = time.perf_counter()
    hits = store.search(question, k=k)
    ranked, scores = _ranked_ids(hits)
    answer = _extractive_answer(
        hits,
        min_score=retrieval_min_similarity,
    )
    contexts = [hit.content for hit in hits if hit.score >= 0.05]
    grounded = groundedness_score(answer, contexts)
    relevance = relevance_score(answer, expected_answer)
    halluc = hallucination_rate(answer, contexts)
    confidence = safe_compute_confidence(
        scores,
        grounded,
        len(answer),
        bool(ranked),
        retrieval_min_similarity=retrieval_min_similarity,
        escalation_threshold=escalation_threshold,
    )
    pattern = match_escalation(question)
    should_escalate = confidence.score < escalation_threshold or pattern is not None
    # Cheap token estimate for cost extrapolation (chars/4 heuristic).
    prompt_tokens = max(1, len(question) // 4 + 200)
    completion_tokens = max(1, len(answer) // 4)
    cost = estimate_cost_usd(
        model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    latency = time.perf_counter() - started
    # Correctness for calibration: gold source hit OR high relevance.
    gold = set(expected_sources)
    correct = bool(gold.intersection(ranked[:1])) or relevance >= 0.35
    if not gold:
        # Abstain-style items: correct when the stand-in refuses to invent.
        correct = answer == _ABSTAIN
    return EvalPrediction(
        question_id=question_id,
        ranked_doc_ids=ranked,
        retrieval_scores=scores,
        answer=answer,
        groundedness=grounded,
        relevance=relevance,
        hallucination=halluc,
        confidence=confidence.score,
        should_escalate=should_escalate,
        latency_seconds=latency,
        cost_usd=cost,
        correct=correct,
    )
