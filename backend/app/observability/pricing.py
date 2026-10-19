"""Load per-model token prices from YAML (not hardcoded)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_PRICES_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "model_prices.yaml"
)


@lru_cache(maxsize=1)
def _load_prices() -> dict[str, Any]:
    with _PRICES_PATH.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("model_prices.yaml must be a mapping")
    return data


def clear_price_cache() -> None:
    """Test helper — reload YAML after fixture edits."""
    _load_prices.cache_clear()


def price_per_1k(model: str) -> tuple[float, float]:
    """Return ``(prompt_usd_per_1k, completion_usd_per_1k)``."""
    data = _load_prices()
    models = data.get("models") or {}
    entry = models.get(model) or data.get("default") or {}
    prompt = float(entry.get("prompt", 0.0))
    completion = float(entry.get("completion", 0.0))
    return prompt, completion


def estimate_cost_usd(
    model: str,
    *,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Estimate USD cost for a single completion."""
    prompt_rate, completion_rate = price_per_1k(model)
    return (prompt_tokens / 1000.0) * prompt_rate + (
        completion_tokens / 1000.0
    ) * completion_rate
