from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-secret-change-me-in-production"


class Settings(BaseSettings):
    """App settings, read from environment variables (and a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Daisytoons API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://daisytoons:daisytoons@localhost:5432/daisytoons"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # Every price is in this one currency (ISO 4217 code): Sri Lankan rupees.
    currency: str = "LKR"

    jwt_secret: str = DEV_JWT_SECRET
    jwt_expire_minutes: int = 60

    @model_validator(mode="after")
    def _require_real_secret_in_production(self) -> "Settings":
        if self.environment == "production" and (
            self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32
        ):
            raise ValueError("JWT_SECRET must be set to at least 32 characters in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
