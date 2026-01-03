"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from redis.asyncio import ConnectionPool, Redis

from app.config import Settings, get_settings
from app.services.booking_client import BookingClient
from app.services.encryption import EncryptionService
from app.services.session_manager import SessionManager, SessionNotFoundError

# Redis connection pool (module-level singleton)
_redis_pool: Optional[ConnectionPool] = None

# HTTP Bearer token security scheme
security = HTTPBearer()


@lru_cache
def get_encryption_service() -> EncryptionService:
    """Get cached encryption service instance."""
    settings = get_settings()
    return EncryptionService(settings.shared_secret)


def get_settings_dependency() -> Settings:
    """Dependency for injecting settings into routes."""
    return get_settings()


async def get_redis_pool() -> ConnectionPool:
    """
    Get or create Redis connection pool.

    Returns:
        ConnectionPool: Shared Redis connection pool
    """
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=10,
        )
    return _redis_pool


async def get_redis() -> Redis:
    """
    Get Redis client from pool.

    Returns:
        Redis: Async Redis client instance
    """
    pool = await get_redis_pool()
    return Redis(connection_pool=pool)


async def close_redis_pool() -> None:
    """Close Redis connection pool (for application shutdown)."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None


async def get_session_manager(
    redis: Redis = Depends(get_redis),
) -> SessionManager:
    """
    Get SessionManager instance.

    Args:
        redis: Redis client from dependency injection

    Returns:
        SessionManager: Session manager instance
    """
    return SessionManager(redis)


async def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session_manager: SessionManager = Depends(get_session_manager),
) -> dict:
    """
    Validate Bearer token and return session data.

    This dependency extracts the Bearer token from the Authorization header,
    validates it against Redis, and returns the session data if valid.

    Args:
        credentials: HTTP Bearer credentials from Authorization header
        session_manager: Session manager instance

    Returns:
        dict: Session data containing cookies, base_url, and created_at

    Raises:
        HTTPException: 401 Unauthorized if token is invalid or expired
    """
    try:
        return await session_manager.get_session(credentials.credentials)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_booking_client(
    session: dict = Depends(get_current_session),
) -> AsyncGenerator[BookingClient, None]:
    """
    Provide BookingClient with session cookies.

    The client is initialized with cookies from the user's session,
    allowing authenticated requests to the booking website.

    Args:
        session: Session data from get_current_session dependency

    Yields:
        BookingClient: Configured booking client instance

    Example:
        @router.get("/times")
        async def get_times(client: BookingClient = Depends(get_booking_client)):
            return await client.get_availability("22-01-2024")
    """
    client = BookingClient(
        base_url=session["base_url"],
        cookies=session.get("cookies"),
    )
    async with client:
        yield client
