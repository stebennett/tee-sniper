"""Session management service using Redis for storage."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class SessionError(Exception):
    """Base exception for session operations."""

    pass


class SessionNotFoundError(SessionError):
    """Session does not exist or has expired."""

    pass


class SessionManager:
    """Manages user sessions in Redis with sliding window TTL."""

    KEY_PREFIX = "session:"
    DEFAULT_TTL = 1800  # 30 minutes

    def __init__(self, redis: Redis, ttl: int = DEFAULT_TTL):
        """
        Initialize SessionManager.

        Args:
            redis: Async Redis client instance
            ttl: Session time-to-live in seconds (default: 30 minutes)
        """
        self.redis = redis
        self.ttl = ttl

    def _key(self, token: str) -> str:
        """Generate Redis key for session token."""
        return f"{self.KEY_PREFIX}{token}"

    async def store_session(self, cookies: dict, base_url: str) -> str:
        """
        Store session cookies and return access token.

        Args:
            cookies: Dictionary of cookies from authenticated session
            base_url: The base URL of the golf course website

        Returns:
            UUID access token for the session
        """
        token = str(uuid.uuid4())
        session_data = {
            "cookies": cookies,
            "base_url": base_url,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await self.redis.setex(
            self._key(token),
            self.ttl,
            json.dumps(session_data),
        )

        logger.info(
            "Session created",
            extra={"token_prefix": token[:8], "base_url": base_url},
        )
        return token

    async def get_session(self, token: str) -> dict:
        """
        Retrieve session data by token.

        Implements sliding window TTL - refreshes expiry on access.

        Args:
            token: The session access token

        Returns:
            Session data dictionary with keys: cookies, base_url, created_at

        Raises:
            SessionNotFoundError: If session doesn't exist or expired
        """
        key = self._key(token)
        data = await self.redis.get(key)

        if data is None:
            logger.warning(
                "Session not found",
                extra={"token_prefix": token[:8]},
            )
            raise SessionNotFoundError("Session not found or expired")

        # Refresh TTL on access (sliding window)
        await self.redis.expire(key, self.ttl)

        logger.debug(
            "Session accessed",
            extra={"token_prefix": token[:8]},
        )
        return json.loads(data)

    async def delete_session(self, token: str) -> bool:
        """
        Delete session (logout).

        Args:
            token: The session access token

        Returns:
            True if session was deleted, False if it didn't exist
        """
        result = await self.redis.delete(self._key(token))
        deleted = result > 0

        logger.info(
            "Session deleted" if deleted else "Session delete attempted (not found)",
            extra={"token_prefix": token[:8], "deleted": deleted},
        )
        return deleted

    async def session_exists(self, token: str) -> bool:
        """
        Check if session exists without refreshing TTL.

        Args:
            token: The session access token

        Returns:
            True if session exists, False otherwise
        """
        return await self.redis.exists(self._key(token)) > 0

    async def get_ttl(self, token: str) -> int:
        """
        Get remaining TTL for a session.

        Args:
            token: The session access token

        Returns:
            Remaining TTL in seconds, -2 if key doesn't exist, -1 if no TTL set
        """
        return await self.redis.ttl(self._key(token))
