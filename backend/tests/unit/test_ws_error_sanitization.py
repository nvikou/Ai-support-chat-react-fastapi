"""Regression: WebSocket errors must not leak internal exception text.

Attack vector: str(e) in the client payload reveals stack-adjacent
details (SQL, paths, secrets) to any connected browser.
"""

from __future__ import annotations

import logging
import re
import uuid

import pytest

from app.services.ws_errors import build_ws_client_error


UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)


def test_client_error_hides_internal_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "password=SuperSecret; table=users"
    with caplog.at_level(logging.ERROR):
        payload = build_ws_client_error(RuntimeError(secret))

    assert payload["type"] == "error"
    assert secret not in payload["content"]
    assert "RuntimeError" not in payload["content"]
    assert "correlation_id" in payload
    assert UUID_RE.search(payload["content"])
    assert payload["correlation_id"] in payload["content"]
    uuid.UUID(payload["correlation_id"])
    assert any(
        "ws_handler_error" in r.getMessage()
        for r in caplog.records
    )


def test_client_error_uses_provided_correlation_id() -> None:
    cid = str(uuid.uuid4())
    payload = build_ws_client_error(
        ValueError("disk /var/lib/postgres boom"),
        correlation_id=cid,
    )
    assert payload["correlation_id"] == cid
    assert cid in payload["content"]
    assert "/var/lib/postgres" not in payload["content"]
