"""Structured JSON logging for the API process.

Call sites keep using stdlib ``logging`` with ``extra={}``. This module
turns those records into one JSON object per line so production log
pipelines can filter by level, event, and (later) request_id.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

# Bound by the request-id middleware; absent outside an HTTP request.
request_id_ctx: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)

_RESERVED_RECORD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "exc_info",
        "exc_text",
        "thread",
        "threadName",
        "taskName",
        "asctime",
    }
)


def get_request_id() -> str | None:
    """Return the correlation id for the current context, if any."""
    return request_id_ctx.get()


def bind_request_id(request_id: str) -> Token[str | None]:
    """Bind ``request_id`` for the current task/context."""
    return request_id_ctx.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the previous request_id binding."""
    request_id_ctx.reset(token)


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record on a single line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _utc_timestamp(record.created),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id is not None:
            payload["request_id"] = request_id

        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(
                record.exc_info
            ).strip()

        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(
    *,
    level: str = "INFO",
    json_logs: bool = True,
) -> None:
    """Replace root handlers with a stdout JSON (or text) handler.

    Idempotent enough for tests: clears existing root handlers so a
    second call does not duplicate lines.
    """
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s"
            )
        )
    root.addHandler(handler)
    root.setLevel(level.upper())


def _utc_timestamp(created: float) -> str:
    return (
        datetime.fromtimestamp(created, tz=UTC)
        .isoformat()
        .replace("+00:00", "Z")
    )
