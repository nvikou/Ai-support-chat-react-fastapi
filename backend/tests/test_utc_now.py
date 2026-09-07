"""Regression: refuse deprecated naive datetime.utcnow() usage.

datetime.utcnow() is deprecated in Python 3.12 and returns naive
datetimes that break comparisons with aware timestamps.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.timeutils import utc_now


_APP_ROOT = Path(__file__).resolve().parents[1] / "app"
_UTCNOW_RE = re.compile(r"datetime\.utcnow\s*\(")


def test_utc_now_is_timezone_aware() -> None:
    stamp = utc_now()
    assert stamp.tzinfo is not None
    assert stamp.utcoffset() is not None


def test_app_sources_do_not_call_datetime_utcnow() -> None:
    offenders: list[str] = []
    for path in _APP_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if _UTCNOW_RE.search(text):
            offenders.append(
                str(path.relative_to(_APP_ROOT.parent))
            )
    assert offenders == [], (
        "Replace datetime.utcnow() with utc_now() / "
        f"datetime.now(timezone.utc): {offenders}"
    )
