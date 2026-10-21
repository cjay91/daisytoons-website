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

    # S3-compatible object storage for product images. Locally this is SeaweedFS from
    # docker-compose.yml; in production, a hosted provider.
    s3_endpoint_url: str | None = "http://localhost:8333"
    s3_region: str = "us-east-1"
    s3_access_key: str = "dev"
    s3_secret_key: str = "dev"
    s3_bucket: str = "daisytoons-images"
    # Where browsers fetch images from: the bucket's public address, or a CDN in front of it.
    s3_public_base_url: str = "http://localhost:8333/daisytoons-images"
    max_image_bytes: int = 5 * 1024 * 1024

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
