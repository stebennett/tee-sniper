"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="TSA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    session_ttl: int = 1800  # 30 minutes

    # Security - shared secret for credential encryption
    shared_secret: str

    # Golf course booking site
    base_url: str  # Base URL of the golf course booking site

    # Path to JSON file mapping partner IDs to display names.
    # Format: {"id1": "Alice Smith", "id2": "Bob Jones"}
    partners_file: str | None = None

    # Twilio SMS (optional; required only when the worker sends notifications)
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "json"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
