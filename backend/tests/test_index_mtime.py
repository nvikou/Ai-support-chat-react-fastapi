"""Tests for FAISS index mtime reload watcher."""

from __future__ import annotations

from pathlib import Path

from app.services.index_mtime import IndexMtimeWatcher


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _touch_index(directory: Path, payload: bytes) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.faiss").write_bytes(payload)
    (directory / "index.pkl").write_bytes(b"pkl-" + payload)


def test_mtime_reload_skipped_inside_ttl(tmp_path: Path) -> None:
    clock = FakeClock()
    _touch_index(tmp_path, b"v1")
    watcher = IndexMtimeWatcher(
        tmp_path,
        ttl_seconds=3.0,
        clock=clock,
    )
    watcher.mark_loaded()
    _touch_index(tmp_path, b"v2")
    clock.advance(1.0)
    assert watcher.should_reload() is False


def test_mtime_reload_triggered_after_ttl(tmp_path: Path) -> None:
    clock = FakeClock()
    _touch_index(tmp_path, b"v1")
    watcher = IndexMtimeWatcher(
        tmp_path,
        ttl_seconds=3.0,
        clock=clock,
    )
    watcher.mark_loaded()
    _touch_index(tmp_path, b"v2-changed")
    clock.advance(3.0)
    assert watcher.should_reload() is True
    watcher.mark_loaded()
    clock.advance(3.0)
    assert watcher.should_reload() is False
