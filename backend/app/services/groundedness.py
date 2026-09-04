"""Groundedness check via a separate JSON-only LLM call."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Awaitable
from collections.abc import Callable
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)

GROUNDING_SYSTEM = """You are a strict grounding auditor.
Given SOURCE documents and an ANSWER, estimate what fraction of
the answer's factual claims are supported by the sources.

Respond with ONLY compact JSON:
{"groundedness": <float 0..1>, "supported": <int>, "total": <int>}
No markdown, no commentary.
"""


class GroundednessCache:
    """In-memory cache keyed by (question hash, answer hash)."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], float] = {}

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def key(self, question: str, answer: str) -> tuple[str, str]:
        return (self._hash(question), self._hash(answer))

    def get(self, question: str, answer: str) -> float | None:
        return self._store.get(self.key(question, answer))

    def set(self, question: str, answer: str, value: float) -> None:
        self._store[self.key(question, answer)] = value


def parse_groundedness_json(raw: str) -> float:
    """Parse auditor JSON; raise on malformed payloads."""
    text = raw.strip()
    fence = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if fence:
        text = fence.group(0)
    payload = json.loads(text)
    value = float(payload["groundedness"])
    if not 0.0 <= value <= 1.0:
        raise ValueError("groundedness out of range")
    return value


async def assess_groundedness(
    *,
    question: str,
    answer: str,
    documents: list[str],
    invoke_llm: Callable[[list[Any]], Awaitable[str]],
    cache: GroundednessCache | None = None,
    enabled: bool = True,
) -> float:
    """Return groundedness in [0, 1]; skip LLM when disabled.

    ``invoke_llm`` receives chat messages and returns raw text so
    tests can inject a fake without network I/O.
    """
    if not enabled:
        # Neutral mid score when the costly check is off.
        return 0.5

    if cache is not None:
        cached = cache.get(question, answer)
        if cached is not None:
            logger.info(
                "groundedness_cache_hit",
                extra={"event": "groundedness_cache_hit"},
            )
            return cached

    sources = "\n---\n".join(documents) if documents else "(none)"
    messages = [
        SystemMessage(content=GROUNDING_SYSTEM),
        HumanMessage(
            content=(
                f"QUESTION:\n{question}\n\n"
                f"SOURCES:\n{sources}\n\n"
                f"ANSWER:\n{answer}\n"
            )
        ),
    ]
    raw = await invoke_llm(messages)
    score = parse_groundedness_json(raw)

    if cache is not None:
        cache.set(question, answer, score)

    logger.info(
        "groundedness_scored",
        extra={
            "event": "groundedness_scored",
            "groundedness": score,
            "source_count": len(documents),
        },
    )
    return score
