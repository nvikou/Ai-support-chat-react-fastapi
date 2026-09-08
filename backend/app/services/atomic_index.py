"""Atomic publish of FAISS index directories onto the live path."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from app.services.faiss_integrity import DIGEST_FILENAME
from app.services.faiss_integrity import write_index_digest

logger = logging.getLogger(__name__)

_INDEX_ARTIFACTS = ("index.faiss", "index.pkl", DIGEST_FILENAME)


def prepare_staging_dir(live_dir: str | Path) -> Path:
    """Return a clean staging directory beside the live index."""
    live = Path(live_dir)
    live.mkdir(parents=True, exist_ok=True)
    staging = live / ".staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    return staging


def atomic_publish_index(
    staging_dir: str | Path,
    live_dir: str | Path,
) -> None:
    """Replace live artifacts only after staging is complete.

    Writes go to ``staging`` first (including digest). A crash mid-write
    leaves the previous live index untouched. Final step renames each
    artifact into place (os.replace is atomic on the same filesystem).
    """
    staging = Path(staging_dir)
    live = Path(live_dir)
    live.mkdir(parents=True, exist_ok=True)

    for name in ("index.faiss", "index.pkl"):
        if not (staging / name).is_file():
            raise FileNotFoundError(
                f"Staging incomplete: missing {name}"
            )

    write_index_digest(staging)

    for name in _INDEX_ARTIFACTS:
        src = staging / name
        dest = live / name
        os.replace(src, dest)

    # Drop empty staging leftovers; ignore races.
    try:
        shutil.rmtree(staging, ignore_errors=True)
    except OSError:
        pass

    logger.info(
        "faiss_index_published",
        extra={
            "event": "faiss_index_published",
            "path": str(live),
        },
    )
