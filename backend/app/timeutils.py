"""Timezone-aware UTC helpers (avoid deprecated datetime.utcnow)."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone


def utc_now() -> datetime:
    """Return the current UTC time as an aware datetime."""
    return datetime.now(timezone.utc)
