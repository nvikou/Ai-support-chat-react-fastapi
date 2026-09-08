"""Portable exclusive file lock for cross-process FAISS writes."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import TracebackType

logger = logging.getLogger(__name__)


class InterprocessFileLock:
    """Exclusive lock using fcntl (POSIX) or msvcrt (Windows).

    Serializes add_documents + save so concurrent workers cannot
    interleave writes into a corrupt on-disk index.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._handle = None

    def acquire(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(self._path, "a+b")
        if self._handle.tell() == 0:
            self._handle.write(b"\0")
            self._handle.flush()
        self._handle.seek(0)
        if sys.platform == "win32":
            import msvcrt

            # Lock one byte; blocks until available.
            msvcrt.locking(
                self._handle.fileno(),
                msvcrt.LK_LOCK,
                1,
            )
        else:
            import fcntl

            fcntl.flock(
                self._handle.fileno(),
                fcntl.LOCK_EX,
            )
        logger.debug(
            "index_lock_acquired",
            extra={
                "event": "index_lock_acquired",
                "path": str(self._path),
            },
        )

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            self._handle.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(
                    self._handle.fileno(),
                    msvcrt.LK_UNLCK,
                    1,
                )
            else:
                import fcntl

                fcntl.flock(
                    self._handle.fileno(),
                    fcntl.LOCK_UN,
                )
        finally:
            self._handle.close()
            self._handle = None
            logger.debug(
                "index_lock_released",
                extra={
                    "event": "index_lock_released",
                    "path": str(self._path),
                },
            )

    def __enter__(self) -> "InterprocessFileLock":
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()
