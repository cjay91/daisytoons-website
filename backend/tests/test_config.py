from app.config import Settings


def test_settings_read_from_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/1")

    settings = Settings()

    assert settings.environment == "test"
    assert settings.redis_url == "redis://redis:6379/1"
