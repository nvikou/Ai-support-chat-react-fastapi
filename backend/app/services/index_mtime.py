"""Detect on-disk FAISS index changes with a short TTL cache.

Multi-worker setups write a new index on one process; peers must
reload without checking the filesystem on every single query.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

_INDEX_NAMES = ("index.faiss", "index.pkl")


class IndexMtimeWatcher:
    """Return True from ``should_reload`` when index mtime advances."""

    def __init__(
        self,
        persist_dir: str | Path,
        *,
        ttl_seconds: float = 3.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._persist_dir = Path(persist_dir)
        self._ttl_seconds = ttl_seconds
        self._clock = clock or time.monotonic
        self._last_check_at = 0.0
        self._seen_mtime: float | None = None

    def current_mtime(self) -> float:
        """Max mtime of index artifacts (0.0 if none exist yet)."""
        mtimes: list[float] = []
        for name in _INDEX_NAMES:
            path = self._persist_dir / name
            if path.is_file():
                mtimes.append(path.stat().st_mtime)
        return max(mtimes) if mtimes else 0.0

    def mark_loaded(self, mtime: float | None = None) -> None:
        """Record the mtime corresponding to the in-memory index."""
        self._seen_mtime = (
            self.current_mtime() if mtime is None else mtime
        )
        self._last_check_at = self._clock()

    def should_reload(self) -> bool:
        """True when TTL elapsed and on-disk mtime differs from memory."""
        now = self._clock()
        if (now - self._last_check_at) < self._ttl_seconds:
            return False
        self._last_check_at = now
        current = self.current_mtime()
        if self._seen_mtime is None:
            self._seen_mtime = current
            return False
        return current != self._seen_mtime
