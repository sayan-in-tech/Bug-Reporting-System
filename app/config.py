"""Application configuration settings."""

import secrets
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Settings
    app_name: str = "Bug Reporting System"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api"

    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000

    # Database Settings
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bug_tracker"
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_echo: bool = False

    # Redis Settings
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = ""

    # JWT Settings
    jwt_algorithm: str = "RS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    jwt_private_key: str = ""
    jwt_public_key: str = ""

    # Security Settings
    secret_key: str = secrets.token_urlsafe(32)
    cors_origins: str = "http://localhost:3000"

    # Rate Limiting
    rate_limit_per_minute: int = 100
    login_rate_limit_per_minute: int = 5
    account_lockout_threshold: int = 5
    account_lockout_duration_minutes: int = 15

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    # Sentry
    sentry_dsn: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str) -> str:
        """Ensure CORS origins is a string."""
        return v if isinstance(v, str) else ",".join(v)

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
