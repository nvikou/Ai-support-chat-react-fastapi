"""Unit tests for password hashing and JWT access tokens."""

from __future__ import annotations

from datetime import timedelta

from jose import jwt

from app.config import get_settings
from app.security import ALGORITHM
from app.security import create_access_token
from app.security import decode_access_token
from app.security import hash_password
from app.security import hash_refresh_token
from app.security import verify_password
from app.timeutils import utc_now


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("correct-horse-battery")
    assert hashed != "correct-horse-battery"
    assert verify_password("correct-horse-battery", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_access_token_decodes_with_expected_claims() -> None:
    token = create_access_token("user-123", "admin")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_access_token_rejects_wrong_type() -> None:
    settings = get_settings()
    expire = utc_now() + timedelta(minutes=5)
    token = jwt.encode(
        {
            "sub": "user-123",
            "role": "user",
            "type": "refresh",
            "exp": expire,
        },
        settings.secret_key,
        algorithm=ALGORITHM,
    )
    assert decode_access_token(token) is None


def test_access_token_rejects_expired() -> None:
    settings = get_settings()
    expire = utc_now() - timedelta(minutes=1)
    token = jwt.encode(
        {
            "sub": "user-123",
            "role": "user",
            "type": "access",
            "exp": expire,
        },
        settings.secret_key,
        algorithm=ALGORITHM,
    )
    assert decode_access_token(token) is None


def test_refresh_token_hash_is_stable_and_non_reversible() -> None:
    raw = "plain-refresh-token-value"
    first = hash_refresh_token(raw)
    second = hash_refresh_token(raw)
    assert first == second
    assert first != raw
    assert len(first) == 64
