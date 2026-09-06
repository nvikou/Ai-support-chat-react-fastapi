"""Regression: production must reject missing/weak secret defaults.

Attack vector: shipping with secret_key='change-this-in-production'
or Admin123! lets anyone forge JWTs and take over the admin account.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def _build(**overrides) -> Settings:
    base = {
        "openai_api_key": "sk-test",
        "database_url": (
            "postgresql+asyncpg://u:p@localhost/db"
        ),
        "admin_email": "ops@example.com",
        "admin_password": "local-only-password-not-default",
        "secret_key": (
            "development-secret-key-32chars-min"
        ),
        "environment": "development",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_secret_and_admin_fields_have_no_defaults() -> None:
    for name in ("secret_key", "admin_email", "admin_password"):
        assert Settings.model_fields[name].is_required(), name


def test_production_rejects_short_secret_key() -> None:
    with pytest.raises(ValidationError):
        _build(
            environment="production",
            secret_key="too-short-to-be-safe",
        )


def test_production_rejects_known_weak_secret_key() -> None:
    with pytest.raises(ValidationError):
        _build(
            environment="production",
            secret_key="change-this-in-production",
        )


def test_production_rejects_example_env_secret() -> None:
    with pytest.raises(ValidationError):
        _build(
            environment="production",
            secret_key=(
                "change-this-in-production-super-secret-key"
            ),
        )


def test_production_accepts_strong_secret_key() -> None:
    settings = _build(
        environment="production",
        secret_key=(
            "n9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4"
        ),
        cookie_secure=True,
    )
    assert settings.is_production
    assert len(settings.secret_key) >= 32
