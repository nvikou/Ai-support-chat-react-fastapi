"""AI support agent: retrieval, grounded answers, composite confidence."""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.text_splitter import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.schema import Document
from langchain_core.messages import SystemMessage

from app.config import get_settings
from app.exceptions import LLMError
from app.services.confidence import safe_compute_confidence
from app.services.escalation import match_escalation
from app.services.faiss_store import FAISSVectorStore
from app.services.groundedness import GroundednessCache
from app.services.groundedness import assess_groundedness
from app.services.llm_client import get_llm_client
from app.services.prompts import build_system_prompt
from app.services.vector_store import ScoredDocument
from app.services.vector_store import VectorStore

settings = get_settings()
logger = logging.getLogger(__name__)

FAISS_PATH = "./faiss_db"


def split_markdown_text(
    markdown_text: str,
    strip_headers: bool = False,
) -> list[Document]:
    """Découpe un texte Markdown en chunks en suivant les titres."""
    markdown_text = re.sub(
        r" {1,}",
        " ",
        re.sub(r"\n\s*\n", "\n", markdown_text),
    )
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=strip_headers,
    )
    return markdown_splitter.split_text(markdown_text)


def _format_history(history: list[dict]) -> str:
    if not history:
        return "(none)"
    lines: list[str] = []
    for msg in history[-10:]:
        role = "Customer" if msg["role"] == "user" else "Agent"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


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
            api_key=settings.openai_api_key,
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
            api_key=settings.openai_api_key,
            model=model,
            temperature=0.3,
        )

    def _retrieve(
        self,
        question: str,
        k: int = 5,
    ) -> list[ScoredDocument]:
        return self.vector_store.search(question, k=k)

    async def answer(
        self,
        question: str,
        history: list[dict],
    ) -> dict:
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
            response = await llm.ainvoke(
                [SystemMessage(content=prompt_body)]
            )
            content = response.content
            if isinstance(content, list):
                return "".join(str(part) for part in content)
            return str(content)

        try:
            call = await self.llm_client.invoke(_operation)
        except LLMError as exc:
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
            }

        answer_text = call.value.strip()
        sources = list({
            str(hit.metadata.get("source", "Knowledge Base"))
            for hit in hits
        })

        try:
            groundedness = await self._score_groundedness(
                question=question,
                answer=answer_text,
                documents=[hit.content for hit in hits],
                model=call.model,
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

        confidence = safe_compute_confidence(
            retrieval_scores,
            groundedness,
            len(answer_text),
            bool(sources),
            retrieval_min_similarity=(
                settings.retrieval_min_similarity
            ),
            escalation_threshold=(
                settings.confidence_escalation_threshold
            ),
            uncertainty_threshold=(
                settings.confidence_uncertainty_threshold
            ),
        )

        pattern_match = match_escalation(question)
        should_escalate = (
            confidence.score
            < settings.confidence_escalation_threshold
            or pattern_match is not None
            or call.degraded
        )

        escalation_reason = None
        if should_escalate:
            if call.degraded:
                escalation_reason = (
                    "Answer served via fallback model "
                    f"({call.model}) — verify with a human"
                )
            elif pattern_match is not None:
                escalation_reason = pattern_match.reason
            else:
                escalation_reason = confidence.reason

        return {
            "answer": answer_text,
            "confidence": confidence.score,
            "confidence_band": confidence.band,
            "confidence_signals": confidence.signals,
            "sources": sources,
            "should_escalate": should_escalate,
            "escalation_reason": escalation_reason,
            "degraded": call.degraded,
        }

    async def _score_groundedness(
        self,
        *,
        question: str,
        answer: str,
        documents: list[str],
        model: str,
    ) -> float:
        llm = self._build_llm(model)

        async def _invoke(messages: list) -> str:
            async def _op(_model: str) -> str:
                response = await llm.ainvoke(messages)
                content = response.content
                if isinstance(content, list):
                    return "".join(str(part) for part in content)
                return str(content)

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
            with open(
                file_path,
                "r",
                encoding="utf-8",
                errors="ignore",
            ) as handle:
                content = handle.read()
            chunks = split_markdown_text(content, strip_headers=False)
            for chunk in chunks:
                chunk.metadata["source"] = filename

            if len(chunks) <= 1:
                loader = TextLoader(file_path, encoding="utf-8")
                documents = loader.load()
                for doc in documents:
                    doc.metadata["source"] = filename
                chunks = self.fallback_splitter.split_documents(
                    documents,
                )

        return self.vector_store.add_documents(
            _chunks_to_store_docs(chunks),
        )

    async def add_faq_entries(self, entries: list[dict]) -> int:
        docs = [
            {
                "content": (
                    f"Q: {e['question']}\nA: {e['answer']}"
                ),
                "metadata": {
                    "source": "FAQ",
                    "category": e.get("category", "general"),
                },
            }
            for e in entries
        ]
        return self.vector_store.add_documents(docs)


_agent_instance: SupportAgent | None = None


def get_agent() -> SupportAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = SupportAgent()
    return _agent_instance
