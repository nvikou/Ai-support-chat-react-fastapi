"""Redact secrets and user chat content from log records.

A structured log that still contains API keys or customer messages is
an incident waiting to happen. This filter runs on every record before
formatting so JSON and text handlers share the same policy.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

REDACTED = "***"

# Exact key match after lowercasing and stripping non-alnum separators.
_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "secretkey",
        "apikey",
        "openaiapikey",
        "accesstoken",
        "refreshtoken",
        "authorization",
        "cookie",
        "adminpassword",
        "token",
        "bearer",
        # User-authored text must never appear in logs.
        "content",
        "message",
        "usermessage",
        "prompt",
        "messages",
        "input",
        "query",
        "question",
    }
)

_BEARER_RE = re.compile(
    r"(?i)\b(bearer)\s+[A-Za-z0-9\-._~+/]+=*",
)
_OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")


def normalize_key(key: str) -> str:
    """Collapse ``api_key`` / ``api-key`` / ``apiKey`` to ``apikey``."""
    return re.sub(r"[^a-z0-9]", "", key.lower())


def is_sensitive_key(key: str) -> bool:
    return normalize_key(key) in _SENSITIVE_KEYS


def redact_string(value: str) -> str:
    """Mask credential-shaped substrings inside free-form text."""
    redacted = _BEARER_RE.sub(r"\1 " + REDACTED, value)
    redacted = _OPENAI_KEY_RE.sub(REDACTED, redacted)
    return _JWT_RE.sub(REDACTED, redacted)


def redact_value(key: str, value: Any) -> Any:
    """Redact ``value`` when ``key`` is sensitive or recurse into maps."""
    if is_sensitive_key(key):
        return REDACTED
    if isinstance(value, dict):
        return {
            child_key: redact_value(child_key, child_val)
            for child_key, child_val in value.items()
        }
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(key, item) for item in value)
    if isinstance(value, str):
        return redact_string(value)
    return value


class RedactionFilter(logging.Filter):
    """Mutate a ``LogRecord`` so secrets never reach the formatter."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_string(record.msg)

        if record.args:
            record.args = _redact_args(record.args)

        for key, value in list(record.__dict__.items()):
            if key.startswith("_"):
                continue
            if key in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "taskName",
                "message",
                "asctime",
            }:
                continue
            record.__dict__[key] = redact_value(key, value)
        return True


def _redact_args(
    args: tuple[Any, ...] | Mapping[str, Any],
) -> tuple[Any, ...] | dict[str, Any]:
    if isinstance(args, Mapping):
        return {key: redact_value(key, value) for key, value in args.items()}
    return tuple(redact_value("", value) for value in args)
