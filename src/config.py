from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables (and a .env
    file when present). Add new settings here as typed fields so there is a
    single, documented place for configuration."""

    # Database connection string (env var SQLALCHEMY_DATABASE_URL, case-insensitive).
    # Intentionally has NO default: a missing value raises at startup ("fail
    # fast") instead of silently connecting somewhere unexpected. Tests inject a
    # dummy value (see tests/conftest.py); Docker provides it via the env.
    sqlalchemy_database_url: str

    # Deployment environment. Used to gate dev-only behavior (e.g. exposing /docs)
    # later on. Keep to a small known set.
    environment: str = "dev"

    # Root log level (DEBUG/INFO/WARNING/ERROR). Consumed by the logging setup.
    log_level: str = "INFO"

    # Metadata surfaced in the OpenAPI docs (title/version on the FastAPI app).
    app_name: str = "Finance Notes & Watchlist API"
    app_version: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
