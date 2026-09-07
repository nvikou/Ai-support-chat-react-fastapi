"""SHA-256 integrity checks for on-disk FAISS index artifacts."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DIGEST_FILENAME = "index.sha256"
_INDEX_FILES = ("index.faiss", "index.pkl")


class FaissIntegrityError(RuntimeError):
    """Raised when the FAISS index digest is missing or mismatched."""


def _require_index_files(directory: Path) -> list[Path]:
    paths = [directory / name for name in _INDEX_FILES]
    missing = [p.name for p in paths if not p.is_file()]
    if missing:
        raise FaissIntegrityError(
            "FAISS index incomplete; missing: "
            + ", ".join(missing)
        )
    return paths


def compute_index_digest(directory: str | Path) -> str:
    """Hash index.faiss + index.pkl in a stable order.

    Why: FAISS load_local unpickles index.pkl. A digest covering both
    artifacts detects tampering before deserialization runs.
    """
    root = Path(directory)
    hasher = hashlib.sha256()
    for path in _require_index_files(root):
        hasher.update(path.name.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def write_index_digest(directory: str | Path) -> str:
    """Persist the current digest next to the index files."""
    root = Path(directory)
    digest = compute_index_digest(root)
    digest_path = root / DIGEST_FILENAME
    digest_path.write_text(digest + "\n", encoding="utf-8")
    logger.info(
        "faiss_digest_written",
        extra={
            "event": "faiss_digest_written",
            "path": str(digest_path),
            "digest": digest,
        },
    )
    return digest


def verify_index_digest(directory: str | Path) -> str:
    """Return the digest if it matches; otherwise refuse to load."""
    root = Path(directory)
    digest_path = root / DIGEST_FILENAME
    if not digest_path.is_file():
        raise FaissIntegrityError(
            "FAISS integrity digest missing; refusing to "
            "deserialize index"
        )
    expected = digest_path.read_text(encoding="utf-8").strip()
    actual = compute_index_digest(root)
    if not expected or actual != expected:
        logger.error(
            "faiss_digest_mismatch",
            extra={
                "event": "faiss_digest_mismatch",
                "expected": expected,
                "actual": actual,
            },
        )
        raise FaissIntegrityError(
            "FAISS integrity digest mismatch; refusing to "
            "deserialize index"
        )
    return actual
