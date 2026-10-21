import pytest

from app.config import Settings


def test_settings_read_from_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/1")

    settings = Settings()

    assert settings.environment == "test"
    assert settings.redis_url == "redis://redis:6379/1"


def test_production_requires_a_real_jwt_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings()

    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    assert Settings().jwt_secret == "x" * 32
