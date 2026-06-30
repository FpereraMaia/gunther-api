from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    # Comma-separated list of allowed CORS origins.
    # Set to exact origins in production, e.g. CORS_ORIGINS=https://app.example.com
    cors_origins: list[str] = ["*"]

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Sentry ────────────────────────────────────────────────────────────────
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)

    # ── OpenTelemetry ─────────────────────────────────────────────────────────
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "gunther_api"
    otel_service_version: str = "0.1.0"
    otel_environment: str = "development"

    # ── JWT ───────────────────────────────────────────────────────────────────
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # ── Octopus ───────────────────────────────────────────────────────────────
    octopus_api_url: str = "http://localhost:8888"

    # ── Authentik dev bypass ──────────────────────────────────────────────────
    # Set DEV_USER_UID in .env during local development to skip Authentik.
    # Leave empty in production — the proxy headers will be present instead.
    dev_user_uid: str = ""
    dev_user_username: str = "dev"
    dev_user_email: str = "dev@localhost"
    dev_user_groups: list[str] = []

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


settings = Settings()
