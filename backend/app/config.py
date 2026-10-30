from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-secret-change-me-in-production"
DEV_PAYHERE_SECRET = "dev-only-payhere-secret"


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

    # Where this API and the storefront are reached from a browser. Used for payment and
    # email links.
    api_public_url: str = "http://localhost:8000"
    storefront_url: str = "http://localhost:3000"

    # Charges, in rupees.
    delivery_fee_colombo: Decimal = Decimal("400")
    delivery_fee_other: Decimal = Decimal("650")
    free_delivery_over: Decimal = Decimal("10000")
    gift_wrap_fee: Decimal = Decimal("250")
    # How long checkout holds stock for an unpaid order.
    reservation_minutes: int = 30

    # "fake" is a built-in stand-in gateway for local development; "payhere" is the real one.
    payment_provider: Literal["fake", "payhere"] = "fake"
    payhere_merchant_id: str = "1200000"
    payhere_merchant_secret: str = DEV_PAYHERE_SECRET
    payhere_sandbox: bool = True

    # Outgoing email. Locally this is Mailpit from docker-compose.yml.
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_starttls: bool = False
    email_from: str = "Daisytoons <orders@daisytoons.lk>"

    # Staff must set up two-step login before they can use the console.
    require_staff_two_factor: bool = False
    # Error tracking: errors are sent to Sentry when this is set.
    sentry_dsn: str | None = None

    # Agents (Claude). Without a key, agents can only run against the scripted test model.
    anthropic_api_key: str | None = None
    agent_model: str = "claude-opus-5-5"

    # Search for agents (Part 9). "auto" uses Voyage AI when VOYAGE_API_KEY is set, and otherwise
    # "hashing", a built-in stand-in that needs no account, for development and tests.
    embedding_provider: Literal["auto", "voyage", "hashing"] = "auto"
    voyage_api_key: str | None = None
    embedding_model: str = "voyage-3.5-lite"
    shop_email: str = "orders@daisytoons.lk"

    @model_validator(mode="after")
    def _require_real_secrets_in_production(self) -> "Settings":
        if self.environment != "production":
            return self
        if self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be set to at least 32 characters in production")
        if self.payment_provider != "payhere":
            raise ValueError("PAYMENT_PROVIDER must be payhere in production")
        if self.payhere_merchant_secret == DEV_PAYHERE_SECRET:
            raise ValueError("PAYHERE_MERCHANT_SECRET must be set in production")
        if not self.require_staff_two_factor:
            raise ValueError("REQUIRE_STAFF_TWO_FACTOR must be true in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
