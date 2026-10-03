"""Prometheus metrics registry, scrape endpoint, and LLM wiring."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.exceptions import LLMTimeout
from app.observability.metrics import (
    classify_escalation_reason,
    extract_token_usage,
    get_metrics,
    reset_metrics_for_tests,
)
from app.observability.pricing import estimate_cost_usd
from tests.unit.test_llm_client import FakeSettings, _client


@pytest.fixture(autouse=True)
def _clean_metrics() -> None:
    reset_metrics_for_tests()


def test_estimate_cost_uses_yaml_rates() -> None:
    # gpt-4o-mini: 0.00015 / 0.0006 per 1k
    cost = estimate_cost_usd(
        "gpt-4o-mini",
        prompt_tokens=1000,
        completion_tokens=1000,
    )
    assert cost == pytest.approx(0.00075)


def test_extract_token_usage_from_usage_metadata() -> None:
    response = SimpleNamespace(
        usage_metadata={
            "input_tokens": 12,
            "output_tokens": 34,
        },
        response_metadata={},
    )
    assert extract_token_usage(response) == (12, 34)


def test_classify_escalation_reason_priority() -> None:
    assert (
        classify_escalation_reason(llm_unavailable=True, degraded=True)
        == "llm_unavailable"
    )
    assert classify_escalation_reason(degraded=True) == "degraded"
    assert classify_escalation_reason(pattern_matched=True) == "pattern"
    assert classify_escalation_reason() == "low_confidence"


def test_observe_tokens_increments_cost_counter() -> None:
    metrics = get_metrics()
    metrics.observe_tokens(
        model="gpt-4o-mini",
        prompt_tokens=1000,
        completion_tokens=0,
    )
    tokens = metrics.registry.get_sample_value(
        "llm_tokens_total",
        {"model": "gpt-4o-mini", "type": "prompt"},
    )
    assert tokens == 1000
    cost = metrics.registry.get_sample_value(
        "llm_cost_usd_total",
        {"model": "gpt-4o-mini"},
    )
    assert cost == pytest.approx(0.00015)


@pytest.mark.asyncio
async def test_llm_client_records_success_duration() -> None:
    client, _sleep, _clock = _client(
        FakeSettings(openai_max_retries=1),
    )

    async def _ok(_model: str) -> str:
        return "ok"

    await client.invoke(_ok)
    sample = get_metrics().registry.get_sample_value(
        "llm_request_duration_seconds_count",
        {"model": "gpt-4o", "status": "success"},
    )
    assert sample == 1
    assert (
        get_metrics().registry.get_sample_value("circuit_breaker_state") == 0.0
    )


@pytest.mark.asyncio
async def test_llm_client_records_timeout_error() -> None:
    client, _sleep, _clock = _client(
        FakeSettings(
            openai_max_retries=1,
            openai_fallback_model="gpt-4o",
        ),
    )

    async def _boom(_model: str) -> str:
        raise LLMTimeout("slow")

    with pytest.raises(LLMTimeout):
        await client.invoke(_boom)

    errors = get_metrics().registry.get_sample_value(
        "llm_errors_total",
        {"error_type": "LLMTimeout"},
    )
    assert errors == 1
    failed = get_metrics().registry.get_sample_value(
        "llm_request_duration_seconds_count",
        {"model": "gpt-4o", "status": "error"},
    )
    assert failed == 1


@pytest.mark.asyncio
async def test_llm_client_records_degraded_status() -> None:
    client, _sleep, _clock = _client(
        FakeSettings(
            openai_max_retries=1,
            openai_fallback_model="gpt-4o-mini",
        ),
    )
    calls = {"n": 0}

    async def _flaky(model: str) -> str:
        calls["n"] += 1
        if model == "gpt-4o":
            raise LLMTimeout("primary down")
        return "fallback-ok"

    result = await client.invoke(_flaky)
    assert result.degraded is True
    sample = get_metrics().registry.get_sample_value(
        "llm_request_duration_seconds_count",
        {"model": "gpt-4o-mini", "status": "degraded"},
    )
    assert sample == 1


@pytest.mark.asyncio
async def test_support_agent_records_rag_confidence_escalation() -> None:
    from app.agent import SupportAgent
    from app.services.vector_store import InMemoryVectorStore
    from tests.fakes import FakeLLMClient

    class _FakeChat:
        async def ainvoke(self, _messages: object) -> SimpleNamespace:
            return SimpleNamespace(
                content="No.",
                usage_metadata={
                    "input_tokens": 11,
                    "output_tokens": 3,
                },
                response_metadata={},
            )

    agent = SupportAgent(vector_store=InMemoryVectorStore())
    agent.llm_client = FakeLLMClient()
    agent._build_llm = (  # type: ignore[method-assign]
        lambda _model: _FakeChat()
    )

    result = await agent.answer("unknown topic please", [])
    assert result["should_escalate"] is True
    assert (
        get_metrics().registry.get_sample_value(
            "rag_retrieval_duration_seconds_count"
        )
        == 1
    )
    assert (
        get_metrics().registry.get_sample_value("rag_confidence_score_count")
        == 1
    )
    assert (
        get_metrics().registry.get_sample_value(
            "conversations_escalated_total",
            {"reason": "low_confidence"},
        )
        == 1
    )
    assert (
        get_metrics().registry.get_sample_value(
            "llm_tokens_total",
            {"model": "fake-primary", "type": "prompt"},
        )
        == 11
    )


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_metric_names(
    client: AsyncClient,
) -> None:
    get_metrics().observe_escalation("low_confidence")
    get_metrics().observe_confidence(0.42)
    get_metrics().observe_retrieval(0.01)

    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    for name in (
        "llm_request_duration_seconds",
        "llm_tokens_total",
        "llm_cost_usd_total",
        "rag_retrieval_duration_seconds",
        "rag_confidence_score",
        "conversations_escalated_total",
        "llm_errors_total",
        "circuit_breaker_state",
    ):
        assert name in body
    assert 'reason="low_confidence"' in body
