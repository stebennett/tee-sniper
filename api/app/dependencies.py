"""FastAPI dependency injection providers."""

from functools import lru_cache

from app.config import Settings, get_settings
from app.services.encryption import EncryptionService


@lru_cache
def get_encryption_service() -> EncryptionService:
    """Get cached encryption service instance."""
    settings = get_settings()
    return EncryptionService(settings.shared_secret)


def get_settings_dependency() -> Settings:
    """Dependency for injecting settings into routes."""
    return get_settings()
