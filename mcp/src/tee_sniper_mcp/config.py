"""Environment-based configuration for the MCP server."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    """Validated server configuration."""

    api_base_url: str
    username: str
    pin: str = field(repr=False)
    shared_secret: str = field(repr=False)
    time_bands_override: dict[str, list[str]] | None


_REQUIRED = (
    "TSA_API_BASE_URL",
    "TSA_USERNAME",
    "TSA_PIN",
    "TSA_SHARED_SECRET",
)


def load_config() -> Config:
    """Load configuration from environment, raising ConfigError on problems."""
    missing = [name for name in _REQUIRED if not os.environ.get(name)]
    if missing:
        raise ConfigError(f"Missing required env vars: {', '.join(missing)}")

    bands_raw = os.environ.get("TSA_TIME_BANDS")
    bands_override: dict[str, list[str]] | None = None
    if bands_raw:
        try:
            parsed = json.loads(bands_raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"TSA_TIME_BANDS is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ConfigError("TSA_TIME_BANDS must be a JSON object")
        bands_override = parsed

    return Config(
        api_base_url=os.environ["TSA_API_BASE_URL"].rstrip("/"),
        username=os.environ["TSA_USERNAME"],
        pin=os.environ["TSA_PIN"],
        shared_secret=os.environ["TSA_SHARED_SECRET"],
        time_bands_override=bands_override,
    )
