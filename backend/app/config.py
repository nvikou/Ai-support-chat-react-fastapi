from pydantic_settings import BaseSettings
from functools import lru_cache


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
    secret_key: str = "change-this-in-production"
    environment: str = "development"
    allowed_origins: str = "http://localhost:3000"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    admin_email: str = "admin@vatecon.com"
    admin_password: str = "Admin123!"
    cookie_secure: bool = False

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
