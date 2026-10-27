"""Error tracking with Sentry. Off unless SENTRY_DSN is set."""

import sentry_sdk

from app.config import get_settings


def init_error_tracking(component: str) -> None:
    settings = get_settings()
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        server_name=component,
        # Errors only, no performance tracing; keeps it inside Sentry's free plan.
        traces_sample_rate=0,
        # Don't send customers' names, emails or addresses along with errors.
        send_default_pii=False,
    )
