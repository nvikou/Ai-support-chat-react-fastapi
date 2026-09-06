"""Bounded, magic-byte-aware upload intake for knowledge files."""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from typing import Protocol

logger = logging.getLogger(__name__)

Kind = Literal["pdf", "text"]
DEFAULT_CHUNK_SIZE = 64 * 1024
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class UploadTooLargeError(Exception):
    """Raised when streamed bytes exceed the configured limit."""

    status_code = 413

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        super().__init__(
            f"Upload exceeds maximum size of {max_bytes} bytes"
        )


class UploadTypeRejectedError(Exception):
    """Raised when magic bytes are not an allowed document type."""

    status_code = 400

    def __init__(self, detail: str = "Unsupported file type") -> None:
        super().__init__(detail)


class AsyncReadable(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True)
class SavedUpload:
    path: str
    kind: Kind
    size: int
    content_hash: str
    suffix: str


def detect_kind_from_magic(header: bytes) -> Kind | None:
    """Infer type from file signature — never from client claims.

    Why magic bytes: content_type and filename are attacker-controlled.
    MZ/ELF payloads advertised as text/plain must be rejected; only
    PDF signatures and NUL-free UTF-8 text are accepted.
    """
    if not header:
        return None
    if header.startswith(b"%PDF"):
        return "pdf"
    if header.startswith((b"MZ", b"\x7fELF")):
        return None
    sample = header[:8192]
    if b"\x00" in sample:
        return None
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return "text"


async def save_upload_streaming(
    upload: AsyncReadable,
    *,
    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    temp_dir: str | Path | None = None,
) -> SavedUpload:
    """Stream an upload to a temp file with an early size cap.

    Size is enforced per chunk so a huge body never fully lands in
    process memory or on disk past the limit.
    """
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")

    hasher = hashlib.sha256()
    total = 0
    header = b""
    kind: Kind | None = None
    tmp_path: str | None = None
    handle = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".upload",
        dir=str(temp_dir) if temp_dir else None,
    )
    tmp_path = handle.name
    try:
        while True:
            chunk = await upload.read(chunk_size)
            if not chunk:
                break
            if total == 0:
                header = chunk[:64]
                kind = detect_kind_from_magic(header)
                if kind is None:
                    raise UploadTypeRejectedError(
                        "File signature is not an allowed "
                        "PDF or text document"
                    )
            total += len(chunk)
            if total > max_bytes:
                raise UploadTooLargeError(max_bytes)
            hasher.update(chunk)
            handle.write(chunk)
        handle.close()

        if total == 0 or kind is None:
            raise UploadTypeRejectedError("Empty or unreadable upload")

        suffix = ".pdf" if kind == "pdf" else ".txt"
        final_path = tmp_path + suffix
        os.replace(tmp_path, final_path)
        tmp_path = final_path

        logger.info(
            "upload_saved",
            extra={
                "event": "upload_saved",
                "kind": kind,
                "size": total,
            },
        )
        return SavedUpload(
            path=final_path,
            kind=kind,
            size=total,
            content_hash=hasher.hexdigest(),
            suffix=suffix,
        )
    except Exception:
        handle.close()
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        # Also remove un-renamed handle path if replace never ran.
        if handle.name and os.path.exists(handle.name):
            os.unlink(handle.name)
        raise
