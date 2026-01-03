"""Tests for configuration loading."""

import os

import pytest

from app.config import Settings, get_settings


class TestSettings:
    """Tests for Settings configuration."""

    def test_settings_loads_from_env(self) -> None:
        """Test that settings loads required values from environment."""
        # Clear cache to force reload
        get_settings.cache_clear()

        settings = get_settings()

        assert settings.shared_secret == "test-shared-secret-for-testing"
        assert settings.redis_url == "redis://localhost:6379/0"
        assert settings.log_level == "DEBUG"

    def test_settings_has_defaults(self) -> None:
        """Test that settings has sensible defaults."""
        get_settings.cache_clear()

        settings = get_settings()

        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8000
        assert settings.debug is False
        assert settings.session_ttl == 1800

    def test_settings_requires_shared_secret(self) -> None:
        """Test that settings fails without shared secret."""
        get_settings.cache_clear()

        # Temporarily remove the shared secret
        original = os.environ.pop("TSA_SHARED_SECRET", None)

        try:
            with pytest.raises(Exception):  # pydantic ValidationError
                Settings()
        finally:
            if original:
                os.environ["TSA_SHARED_SECRET"] = original
            get_settings.cache_clear()

    def test_settings_caching(self) -> None:
        """Test that settings are cached."""
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2
