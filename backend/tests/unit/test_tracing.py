"""OpenTelemetry span helpers and answer-path instrumentation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.util._once import Once

import app.observability.tracing as tracing_mod
from app.agent import SupportAgent
from app.config import get_settings
from app.observability.tracing import setup_tracing, shutdown_tracing, span
from app.services.vector_store import InMemoryVectorStore
from tests.fakes import FakeLLMClient


def _reset_tracer_provider() -> None:
    """Allow tests to replace the global TracerProvider."""
    shutdown_tracing()
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]
    trace._TRACER_PROVIDER_SET_ONCE = Once()  # type: ignore[attr-defined]
    tracing_mod._provider = None


@pytest.fixture
def memory_exporter() -> InMemorySpanExporter:
    _reset_tracer_provider()
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    tracing_mod._provider = provider
    try:
        yield exporter
    finally:
        _reset_tracer_provider()


def test_span_records_name_and_attributes(
    memory_exporter: InMemorySpanExporter,
) -> None:
    with span("unit.probe", **{"probe.ok": True}):
        pass
    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "unit.probe"
    assert spans[0].attributes["probe.ok"] is True


def test_setup_tracing_rejects_unknown_exporter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORTER", "jaeger-legacy")
    get_settings.cache_clear()
    _reset_tracer_provider()
    with pytest.raises(ValueError, match="Unsupported otel_exporter"):
        setup_tracing(get_settings())
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_answer_emits_rag_spans(
    memory_exporter: InMemorySpanExporter,
) -> None:
    class _FakeChat:
        async def ainvoke(self, _messages: object) -> SimpleNamespace:
            return SimpleNamespace(
                content="No.",
                usage_metadata={
                    "input_tokens": 2,
                    "output_tokens": 1,
                },
                response_metadata={},
            )

    agent = SupportAgent(vector_store=InMemoryVectorStore())
    # FakeLLMClient bypasses LLMClient.invoke — assert RAG spans only.
    agent.llm_client = FakeLLMClient()
    agent._build_llm = (  # type: ignore[method-assign]
        lambda _model: _FakeChat()
    )

    await agent.answer("unknown topic", [])
    names = {s.name for s in memory_exporter.get_finished_spans()}
    assert "rag.answer" in names
    assert "rag.retrieval" in names
    assert "rag.confidence" in names
    assert "rag.groundedness" in names


@pytest.mark.asyncio
async def test_llm_client_emits_invoke_span(
    memory_exporter: InMemorySpanExporter,
) -> None:
    from tests.unit.test_llm_client import FakeSettings, _client

    client, _sleep, _clock = _client(FakeSettings(openai_max_retries=1))

    async def _ok(_model: str) -> str:
        return "ok"

    await client.invoke(_ok)
    names = {s.name for s in memory_exporter.get_finished_spans()}
    assert "llm.invoke" in names
