"""Structured logging: JSON shape, request id, secret redaction."""

from __future__ import annotations

import io
import json
import logging
import uuid

import pytest
from httpx import AsyncClient

from app.observability.logging import (
    JsonFormatter,
    bind_request_id,
    configure_logging,
    reset_request_id,
)
from app.observability.middleware import REQUEST_ID_HEADER
from app.observability.redaction import (
    REDACTED,
    RedactionFilter,
    redact_value,
)


def _emit_json(**extra: object) -> dict[str, object]:
    """Format one log line through redaction + JSON formatter."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactionFilter())
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test.structured_logging")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        logger.info("probe", extra=extra)
    finally:
        logger.handlers.clear()
    line = stream.getvalue().strip()
    return json.loads(line)


def test_api_key_in_extra_is_redacted() -> None:
    # Fake credential — asserts redaction, not a real secret.
    fake_key = "sk-live-not-real"  # pragma: allowlist secret
    payload = _emit_json(event="leak_probe", openai_api_key=fake_key)
    assert payload["openai_api_key"] == REDACTED
    assert "sk-live" not in json.dumps(payload)


def test_password_and_token_keys_are_redacted() -> None:
    fake_password = "hunter2"  # pragma: allowlist secret
    fake_access = "tok_abc"  # pragma: allowlist secret
    fake_refresh = "tok_ref"  # pragma: allowlist secret
    payload = _emit_json(
        password=fake_password,
        access_token=fake_access,
        refresh_token=fake_refresh,
    )
    assert payload["password"] == REDACTED
    assert payload["access_token"] == REDACTED
    assert payload["refresh_token"] == REDACTED


def test_user_message_content_is_redacted() -> None:
    # Avoid extra key ``message`` — it clashes with LogRecord.
    payload = _emit_json(
        content="Please refund my order 12345",
        user_message="I am angry about billing",
        prompt="How do I reset my password?",
    )
    assert payload["content"] == REDACTED
    assert payload["user_message"] == REDACTED
    assert payload["prompt"] == REDACTED
    assert "refund" not in json.dumps(payload)
    assert "password?" not in json.dumps(payload)


def test_bearer_and_sk_patterns_in_message_are_redacted() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactionFilter())
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test.structured_logging.msg")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    # Synthetic values only — prove patterns are masked in the message.
    bearer = "Bearer abc.def.ghi"  # pragma: allowlist secret
    sk = "sk-proj-SECRETKEY99"  # pragma: allowlist secret
    secret = f"Authorization {bearer} {sk}"
    try:
        logger.info(secret)
    finally:
        logger.handlers.clear()
    line = stream.getvalue()
    assert "abc.def.ghi" not in line
    assert "sk-proj-SECRETKEY99" not in line
    assert REDACTED in line


def test_nested_dict_redacts_sensitive_keys() -> None:
    redacted = redact_value(
        "payload",
        {"user_id": "u1", "api_key": "sk-nested", "ok": True},
    )
    assert isinstance(redacted, dict)
    assert redacted["user_id"] == "u1"
    assert redacted["api_key"] == REDACTED
    assert redacted["ok"] is True


def test_json_formatter_includes_bound_request_id() -> None:
    token = bind_request_id("req-for-formatter")
    try:
        payload = _emit_json(event="correlated")
    finally:
        reset_request_id(token)
    assert payload["request_id"] == "req-for-formatter"
    assert payload["event"] == "correlated"


def test_configure_logging_attaches_redaction_filter() -> None:
    configure_logging(level="INFO", json_logs=True)
    root = logging.getLogger()
    assert root.handlers
    filters = root.handlers[0].filters
    assert any(isinstance(f, RedactionFilter) for f in filters)


@pytest.mark.asyncio
async def test_health_returns_request_id_header(
    client: AsyncClient,
) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    request_id = response.headers.get(REQUEST_ID_HEADER)
    assert request_id
    uuid.UUID(request_id)


@pytest.mark.asyncio
async def test_health_echoes_safe_client_request_id(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/health",
        headers={REQUEST_ID_HEADER: "client-trace-42"},
    )
    assert response.headers.get(REQUEST_ID_HEADER) == "client-trace-42"
