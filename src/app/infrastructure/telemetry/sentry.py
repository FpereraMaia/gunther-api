"""Sentry error tracking initialization.

Silent no-op when SENTRY_DSN is empty — no import errors, no warnings.
Automatically correlates with OTel trace IDs when both are configured.
"""
from __future__ import annotations

from app.shared.config import Settings


def setup_sentry(settings: Settings) -> None:
    if not settings.sentry_dsn:
        return

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            LoggingIntegration(level=None, event_level=None),
        ],
        environment=settings.otel_environment,
        release=f"{settings.otel_service_name}@{settings.otel_service_version}",
        send_default_pii=False,
    )
