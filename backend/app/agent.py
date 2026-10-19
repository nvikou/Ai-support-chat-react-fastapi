"""AI support agent: retrieval, grounded answers, composite confidence."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings
from app.exceptions import LLMError
from app.observability.metrics import (
    Timer,
    classify_escalation_reason,
    extract_token_usage,
    get_metrics,
)
from app.observability.pricing import estimate_cost_usd
from app.observability.tracing import span
from app.services.chunking import split_markdown_text
from app.services.confidence import safe_compute_confidence
from app.services.escalation import match_escalation
from app.services.faiss_store import FAISSVectorStore
from app.services.groundedness import GroundednessCache, assess_groundedness
from app.services.llm_client import get_llm_client
from app.services.prompts import build_system_prompt
from app.services.vector_metrics import get_vector_metrics
from app.services.vector_store import ScoredDocument, VectorStore

settings = get_settings()
logger = logging.getLogger(__name__)

FAISS_PATH = "./faiss_db"


def _format_history(history: list[dict[str, Any]]) -> str:
    if not history:
        return "(none)"
    lines: list[str] = []
    for msg in history[-10:]:
        role = "Customer" if msg["role"] == "user" else "Agent"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


def _message_text(response: Any) -> str:
    content = response.content
    if isinstance(content, list):
        return "".join(str(part) for part in content)
    return str(content)


def _observe_response_tokens(
    model: str,
    response: Any,
    turn_usage: dict[str, Any],
) -> None:
    prompt_tokens, completion_tokens = extract_token_usage(response)
    turn_usage["prompt_tokens"] = (
        int(turn_usage.get("prompt_tokens", 0)) + prompt_tokens
    )
    turn_usage["completion_tokens"] = (
        int(turn_usage.get("completion_tokens", 0)) + completion_tokens
    )
    turn_usage["model"] = model
    if prompt_tokens or completion_tokens:
        get_metrics().observe_tokens(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


def _usage_fields(turn_usage: dict[str, Any]) -> dict[str, Any]:
    prompt = int(turn_usage.get("prompt_tokens", 0))
    completion = int(turn_usage.get("completion_tokens", 0))
    model = str(turn_usage.get("model") or settings.openai_model)
    return {
        "model": model,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "cost_usd": estimate_cost_usd(
            model,
            prompt_tokens=prompt,
            completion_tokens=completion,
        ),
    }


def _chunks_to_store_docs(
    chunks: list[Document],
) -> list[dict[str, Any]]:
    return [
        {
            "content": chunk.page_content,
            "metadata": dict(chunk.metadata or {}),
        }
        for chunk in chunks
    ]


class SupportAgent:
    def __init__(
        self,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.embeddings = OpenAIEmbeddings(
            api_key=settings.openai_api_key,  # type: ignore[arg-type]
        )
        self.llm = self._build_llm(settings.openai_model)
        self.llm_client = get_llm_client()
        # Production uses FAISSVectorStore (locked atomic writes +
        # mtime reload). Tests inject InMemoryVectorStore.
        self.vector_store: VectorStore = (
            vector_store
            if vector_store is not None
            else FAISSVectorStore(self.embeddings, FAISS_PATH)
        )
        self.fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )
        self._groundedness_cache = GroundednessCache()

    def _build_llm(self, model: str) -> ChatOpenAI:
        return ChatOpenAI(
            # Settings keeps a plain str from env; langchain stubs want
            # SecretStr. Runtime accepts str.
            api_key=settings.openai_api_key,  # type: ignore[arg-type]
            model=model,
            temperature=0.3,
        )

    def _retrieve(
        self,
        question: str,
        k: int = 5,
    ) -> list[ScoredDocument]:
        with span("rag.retrieval", **{"rag.top_k": k}):
            timer = Timer()
            hits = self.vector_store.search(question, k=k)
            get_vector_metrics().record_search()
            get_metrics().observe_retrieval(timer.seconds())
            return hits

    async def answer(
        self,
        question: str,
        history: list[dict[str, Any]],
        *,
        force_fallback: bool = False,
    ) -> dict[str, Any]:
        metrics = get_metrics()
        turn_usage: dict[str, Any] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "model": (
                settings.openai_fallback_model
                if force_fallback
                else settings.openai_model
            ),
        }
        with span(
            "rag.answer",
            **{"llm.force_fallback": force_fallback},
        ):
            return await self._answer_traced(
                question,
                history,
                force_fallback=force_fallback,
                metrics=metrics,
                turn_usage=turn_usage,
            )

    async def _answer_traced(
        self,
        question: str,
        history: list[dict[str, Any]],
        *,
        force_fallback: bool,
        metrics: Any,
        turn_usage: dict[str, Any],
    ) -> dict[str, Any]:
        hits = self._retrieve(question)
        retrieval_scores = [hit.score for hit in hits]
        context = (
            "\n\n".join(hit.content for hit in hits)
            if hits
            else "(no relevant context found)"
        )
        chat_history = _format_history(history)
        # Avoid str.format on user/context text (may contain braces).
        prompt_body = (
            build_system_prompt()
            .replace("{context}", context)
            .replace("{chat_history}", chat_history)
            .replace("{question}", question)
        )

        async def _operation(model: str) -> str:
            llm = self._build_llm(model)
            response = await llm.ainvoke([SystemMessage(content=prompt_body)])
            _observe_response_tokens(model, response, turn_usage)
            return _message_text(response)

        primary = (
            settings.openai_fallback_model
            if force_fallback
            else settings.openai_model
        )
        fallback = settings.openai_fallback_model

        try:
            call = await self.llm_client.invoke(
                _operation,
                primary_model=primary,
                fallback_model=fallback,
            )
        except LLMError as exc:
            metrics.observe_confidence(0.0)
            metrics.observe_escalation(
                classify_escalation_reason(llm_unavailable=True)
            )
            return {
                "answer": (
                    "I'm temporarily unable to process your "
                    "request. Connecting you with a human agent."
                ),
                "confidence": 0.0,
                "confidence_band": "low",
                "confidence_signals": {},
                "sources": [],
                "should_escalate": True,
                "escalation_reason": f"LLM unavailable — {exc}",
                "degraded": True,
                **_usage_fields(turn_usage),
            }

        answer_text = call.value.strip()
        sources = list(
            {str(hit.metadata.get("source", "Knowledge Base")) for hit in hits}
        )

        try:
            with span("rag.groundedness"):
                groundedness = await self._score_groundedness(
                    question=question,
                    answer=answer_text,
                    documents=[hit.content for hit in hits],
                    model=call.model,
                    turn_usage=turn_usage,
                )
        except Exception as exc:
            logger.warning(
                "groundedness_fail_closed",
                extra={
                    "event": "groundedness_fail_closed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            groundedness = 0.0

        with span("rag.confidence") as confidence_span:
            confidence = safe_compute_confidence(
                retrieval_scores,
                groundedness,
                len(answer_text),
                bool(sources),
                retrieval_min_similarity=(settings.retrieval_min_similarity),
                escalation_threshold=(
                    settings.confidence_escalation_threshold
                ),
                uncertainty_threshold=(
                    settings.confidence_uncertainty_threshold
                ),
            )
            confidence_span.set_attribute(
                "rag.confidence_score", confidence.score
            )
            confidence_span.set_attribute(
                "rag.confidence_band", confidence.band
            )
        metrics.observe_confidence(confidence.score)

        pattern_match = match_escalation(question)
        degraded = call.degraded or force_fallback
        should_escalate = (
            confidence.score < settings.confidence_escalation_threshold
            or pattern_match is not None
            or degraded
        )

        escalation_reason = None
        if should_escalate:
            if degraded:
                escalation_reason = (
                    "Answer served via fallback model "
                    f"({call.model}) — verify with a human"
                )
            elif pattern_match is not None:
                escalation_reason = pattern_match.reason
            else:
                escalation_reason = confidence.reason
            metrics.observe_escalation(
                classify_escalation_reason(
                    degraded=degraded,
                    pattern_matched=pattern_match is not None,
                )
            )

        return {
            "answer": answer_text,
            "confidence": confidence.score,
            "confidence_band": confidence.band,
            "confidence_signals": confidence.signals,
            "sources": sources,
            "should_escalate": should_escalate,
            "escalation_reason": escalation_reason,
            "degraded": degraded,
            **_usage_fields(turn_usage),
        }

    async def _score_groundedness(
        self,
        *,
        question: str,
        answer: str,
        documents: list[str],
        model: str,
        turn_usage: dict[str, Any],
    ) -> float:
        llm = self._build_llm(model)

        async def _invoke(messages: list[Any]) -> str:
            async def _op(active_model: str) -> str:
                response = await llm.ainvoke(messages)
                # Auditor tokens must count too or spend is under-reported.
                _observe_response_tokens(
                    active_model,
                    response,
                    turn_usage,
                )
                return _message_text(response)

            # Reuse resilience policies for the auditor call too.
            result = await self.llm_client.invoke(
                _op,
                primary_model=model,
                fallback_model=settings.openai_fallback_model,
            )
            return str(result.value)

        return await assess_groundedness(
            question=question,
            answer=answer,
            documents=documents,
            invoke_llm=_invoke,
            cache=self._groundedness_cache,
            enabled=settings.groundedness_enabled,
        )

    async def ingest_document(
        self,
        file_path: str,
        filename: str,
    ) -> int:
        if filename.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            for doc in documents:
                doc.metadata["source"] = filename
            chunks = self.fallback_splitter.split_documents(documents)
        else:
            content = await asyncio.to_thread(
                Path(file_path).read_text,
                encoding="utf-8",
                errors="ignore",
            )
            chunks = split_markdown_text(content, strip_headers=False)
            for chunk in chunks:
                chunk.metadata["source"] = filename

            if len(chunks) <= 1:
                text_loader = TextLoader(
                    file_path,
                    encoding="utf-8",
                )
                documents = text_loader.load()
                for doc in documents:
                    doc.metadata["source"] = filename
                chunks = self.fallback_splitter.split_documents(
                    documents,
                )

        return self.vector_store.add_documents(
            _chunks_to_store_docs(chunks),
        )

    async def add_faq_entries(self, entries: list[dict[str, Any]]) -> int:
        docs = [
            {
                "content": (f"Q: {e['question']}\nA: {e['answer']}"),
                "metadata": {
                    "source": "FAQ",
                    "category": e.get("category", "general"),
                },
            }
            for e in entries
        ]
        return self.vector_store.add_documents(docs)
