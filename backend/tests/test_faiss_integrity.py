"""Regression: FAISS index must not load if the on-disk digest diverges.

Attack vector: allow_dangerous_deserialization=True unpickles
index.pkl. Anyone who can write the FAISS volume can plant a
malicious pickle and gain code execution on the next process boot.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.faiss_integrity import FaissIntegrityError
from app.services.faiss_integrity import compute_index_digest
from app.services.faiss_integrity import verify_index_digest
from app.services.faiss_integrity import write_index_digest


def _seed_index(directory: Path, *, payload: bytes) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.faiss").write_bytes(payload)
    (directory / "index.pkl").write_bytes(b"pickle-bytes-" + payload)


def test_digest_is_stable_for_unchanged_files(tmp_path: Path) -> None:
    _seed_index(tmp_path, payload=b"abc")
    first = compute_index_digest(tmp_path)
    second = compute_index_digest(tmp_path)
    assert first == second
    assert len(first) == 64


def test_write_and_verify_roundtrip(tmp_path: Path) -> None:
    _seed_index(tmp_path, payload=b"roundtrip")
    digest = write_index_digest(tmp_path)
    assert (tmp_path / "index.sha256").read_text(
        encoding="utf-8"
    ).strip() == digest
    assert verify_index_digest(tmp_path) == digest


def test_tampered_faiss_file_fails_verification(
    tmp_path: Path,
) -> None:
    _seed_index(tmp_path, payload=b"clean")
    write_index_digest(tmp_path)
    (tmp_path / "index.faiss").write_bytes(b"evil-payload")
    with pytest.raises(FaissIntegrityError):
        verify_index_digest(tmp_path)


def test_tampered_pickle_file_fails_verification(
    tmp_path: Path,
) -> None:
    _seed_index(tmp_path, payload=b"clean")
    write_index_digest(tmp_path)
    (tmp_path / "index.pkl").write_bytes(b"malicious-pickle")
    with pytest.raises(FaissIntegrityError):
        verify_index_digest(tmp_path)


def test_missing_digest_fails_closed(tmp_path: Path) -> None:
    _seed_index(tmp_path, payload=b"no-digest")
    with pytest.raises(FaissIntegrityError):
        verify_index_digest(tmp_path)


def test_missing_index_files_fail(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    with pytest.raises(FaissIntegrityError):
        compute_index_digest(tmp_path)
