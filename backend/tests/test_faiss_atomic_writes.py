"""Tests for portable lock and atomic FAISS index publish."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from app.services.atomic_index import atomic_publish_index
from app.services.atomic_index import prepare_staging_dir
from app.services.faiss_integrity import DIGEST_FILENAME
from app.services.faiss_integrity import compute_index_digest
from app.services.file_lock import InterprocessFileLock


def _seed(directory: Path, payload: bytes) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.faiss").write_bytes(payload)
    (directory / "index.pkl").write_bytes(b"pkl-" + payload)


def test_file_lock_serializes_critical_section(tmp_path: Path) -> None:
    lock_path = tmp_path / ".index.lock"
    order: list[str] = []
    barrier = threading.Barrier(2)

    def worker(name: str) -> None:
        barrier.wait()
        with InterprocessFileLock(lock_path):
            order.append(f"{name}-enter")
            order.append(f"{name}-exit")

    threads = [
        threading.Thread(target=worker, args=("a",)),
        threading.Thread(target=worker, args=("b",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert len(order) == 4
    # No interleaving of enter/exit across holders.
    assert order[0].endswith("-enter")
    assert order[1].endswith("-exit")
    assert order[2].endswith("-enter")
    assert order[3].endswith("-exit")


def test_interrupted_staging_leaves_live_index_intact(
    tmp_path: Path,
) -> None:
    live = tmp_path / "live"
    _seed(live, b"v1-good")
    from app.services.faiss_integrity import write_index_digest

    write_index_digest(live)
    original = compute_index_digest(live)

    staging = prepare_staging_dir(live)
    (staging / "index.faiss").write_bytes(b"partial-only")
    # Crash before index.pkl + publish: must not touch live.
    with pytest.raises(FileNotFoundError):
        atomic_publish_index(staging, live)

    assert compute_index_digest(live) == original
    assert (live / "index.faiss").read_bytes() == b"v1-good"


def test_atomic_publish_replaces_live_artifacts(
    tmp_path: Path,
) -> None:
    live = tmp_path / "live"
    _seed(live, b"old")
    from app.services.faiss_integrity import write_index_digest

    write_index_digest(live)

    staging = prepare_staging_dir(live)
    _seed(staging, b"new")
    atomic_publish_index(staging, live)

    assert (live / "index.faiss").read_bytes() == b"new"
    assert (live / DIGEST_FILENAME).is_file()
    assert compute_index_digest(live) == (
        (live / DIGEST_FILENAME).read_text(encoding="utf-8").strip()
    )
