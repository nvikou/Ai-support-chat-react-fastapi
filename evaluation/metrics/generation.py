"""Offline generation proxies (no live LLM judge).

These scores compare a predicted answer to retrieved context and/or
gold text with token overlap. They are honest placeholders until a
judge model is wired; RESULTS.md must call that out.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def groundedness_score(answer: str, contexts: list[str]) -> float:
    """Share of answer tokens that appear in retrieved context."""
    answer_tokens = _tokens(answer)
    if not answer_tokens:
        return 0.0
    if not contexts:
        return 0.0
    ctx_tokens = _tokens(" ".join(contexts))
    if not ctx_tokens:
        return 0.0
    overlap = answer_tokens & ctx_tokens
    return len(overlap) / len(answer_tokens)


def relevance_score(answer: str, expected_answer: str) -> float:
    """Token-overlap F1 between prediction and gold answer."""
    pred = _tokens(answer)
    gold = _tokens(expected_answer)
    if not pred and not gold:
        return 1.0
    if not pred or not gold:
        return 0.0
    overlap = pred & gold
    precision = len(overlap) / len(pred)
    recall = len(overlap) / len(gold)
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def hallucination_rate(
    answer: str,
    contexts: list[str],
    *,
    abstain_phrases: tuple[str, ...] = (
        "do not know",
        "don't know",
        "not in the knowledge",
        "no knowledge-base",
        "outside",
        "out of scope",
        "refuse",
    ),
) -> float:
    """1 - groundedness, unless the answer abstains (then 0)."""
    lowered = answer.lower()
    if any(phrase in lowered for phrase in abstain_phrases):
        return 0.0
    return 1.0 - groundedness_score(answer, contexts)
