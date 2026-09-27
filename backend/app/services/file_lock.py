"""Portable exclusive file lock for cross-process FAISS writes."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import TracebackType
from typing import BinaryIO

logger = logging.getLogger(__name__)


class InterprocessFileLock:
    """Exclusive lock using fcntl (POSIX) or msvcrt (Windows).

    Serializes add_documents + save so concurrent workers cannot
    interleave writes into a corrupt on-disk index.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._handle: BinaryIO | None = None

    def acquire(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self._path, "a+b")
        self._handle = handle
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if sys.platform == "win32":
            import msvcrt

            # Lock one byte; blocks until available.
            msvcrt.locking(
                handle.fileno(),
                msvcrt.LK_LOCK,
                1,
            )
        else:
            import fcntl

            fcntl.flock(
                handle.fileno(),
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
        handle = self._handle
        if handle is None:
            return
        try:
            handle.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(
                    handle.fileno(),
                    msvcrt.LK_UNLCK,
                    1,
                )
            else:
                import fcntl

                fcntl.flock(
                    handle.fileno(),
                    fcntl.LOCK_UN,
                )
        finally:
            handle.close()
            self._handle = None
            logger.debug(
                "index_lock_released",
                extra={
                    "event": "index_lock_released",
                    "path": str(self._path),
                },
            )

    def __enter__(self) -> InterprocessFileLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()
