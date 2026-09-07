import hashlib
import secrets
from datetime import timedelta

import bcrypt
from jose import JWTError, jwt

from app.config import get_settings
from app.timeutils import utc_now

settings = get_settings()

ALGORITHM = "HS256"
REFRESH_COOKIE = "refresh_token"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode(),
        bcrypt.gensalt(),
    ).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str, role: str) -> str:
    expire = utc_now() + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
        )
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def refresh_token_expires_at():
    return utc_now() + timedelta(
        days=settings.refresh_token_expire_days
    )
