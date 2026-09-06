"""Application settings loaded from the environment."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

# Values that must never be used as production JWT signing keys.
_KNOWN_WEAK_SECRET_KEYS = frozenset({
    "change-this-in-production",
    "change-this-in-production-super-secret-key",
    "secret",
    "secret_key",
    "password",
    "admin",
    "changeme",
})


class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-4o"
    openai_fallback_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 30.0
    openai_max_retries: int = 3
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_seconds: float = 60.0
    # Composite confidence (not LLM self-scores)
    confidence_escalation_threshold: float = 0.5
    confidence_uncertainty_threshold: float = 0.7
    retrieval_min_similarity: float = 0.35
    groundedness_enabled: bool = True
    database_url: str
    redis_url: str = "redis://localhost:6379"
    # Required — no insecure defaults (forgeable JWTs / shared admin).
    secret_key: str
    environment: str = "development"
    allowed_origins: str = "http://localhost:3000"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    admin_email: str
    admin_password: str
    cookie_secure: bool = False

    model_config = SettingsConfigDict(env_file=".env")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @model_validator(mode="after")
    def reject_weak_production_secrets(self) -> "Settings":
        """Refuse to boot production with a forgeable signing key."""
        if not self.is_production:
            return self
        key = (self.secret_key or "").strip()
        if not key:
            raise ValueError(
                "SECRET_KEY is required in production"
            )
        if len(key) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters "
                "in production"
            )
        if key in _KNOWN_WEAK_SECRET_KEYS:
            raise ValueError(
                "SECRET_KEY matches a known insecure default "
                "and cannot be used in production"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
