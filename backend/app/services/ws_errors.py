"""Safe WebSocket error payloads for clients."""

from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


def build_ws_client_error(
    exc: BaseException,
    *,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Log the full exception; return a generic client-safe payload.

    Never include ``str(exc)`` in the returned content: that leaks
    internals (SQL, paths, credentials) to the browser.
    """
    cid = correlation_id or str(uuid.uuid4())
    logger.error(
        "ws_handler_error",
        exc_info=exc,
        extra={
            "event": "ws_handler_error",
            "correlation_id": cid,
            "error_type": type(exc).__name__,
        },
    )
    return {
        "type": "error",
        "content": (
            "An unexpected error occurred. "
            f"Reference: {cid}"
        ),
        "correlation_id": cid,
    }
