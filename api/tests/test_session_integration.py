"""Integration tests for session management with real Redis.

These tests require a running Redis instance. They will be skipped if Redis
is not available. Use docker-compose to start Redis:

    docker-compose up -d redis

"""

import asyncio
import os

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError

from app.services.session_manager import SessionManager, SessionNotFoundError


def redis_available() -> bool:
    """Check if Redis is available for integration tests."""
    try:
        # Use environment variable directly to avoid import issues at collection time
        redis_url = os.environ.get("TSA_REDIS_URL", "redis://localhost:6379/0")
        redis = Redis.from_url(redis_url)
        # Run synchronously using asyncio
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(redis.ping())
            return True
        finally:
            loop.run_until_complete(redis.close())
            loop.close()
    except (ConnectionError, OSError, Exception):
        return False


# Skip all tests in this module if Redis is not available
pytestmark = pytest.mark.skipif(
    not redis_available(),
    reason="Redis not available for integration tests",
)


@pytest.fixture
async def redis_client():
    """Create a real Redis client for integration testing."""
    redis_url = os.environ.get("TSA_REDIS_URL", "redis://localhost:6379/0")
    redis = Redis.from_url(redis_url, decode_responses=True)
    yield redis
    await redis.close()


@pytest.fixture
async def session_manager(redis_client):
    """Create a SessionManager with real Redis."""
    return SessionManager(redis_client, ttl=5)  # Short TTL for testing


@pytest.fixture(autouse=True)
async def cleanup_sessions(redis_client):
    """Clean up test sessions before and after each test."""
    # Clean before test
    keys = await redis_client.keys("session:*")
    if keys:
        await redis_client.delete(*keys)

    yield

    # Clean after test
    keys = await redis_client.keys("session:*")
    if keys:
        await redis_client.delete(*keys)


class TestSessionLifecycle:
    """Integration tests for full session lifecycle."""

    @pytest.mark.asyncio
    async def test_full_session_lifecycle(self, session_manager):
        """Test complete session flow: store -> get -> delete."""
        cookies = {"PHPSESSID": "integration-test-123", "auth": "token-value"}
        base_url = "https://integration-test.example.com/"

        # Store session
        token = await session_manager.store_session(cookies, base_url)
        assert token is not None
        assert len(token) == 36  # UUID format

        # Get session
        session = await session_manager.get_session(token)
        assert session["cookies"] == cookies
        assert session["base_url"] == base_url
        assert "created_at" in session

        # Verify session exists
        exists = await session_manager.session_exists(token)
        assert exists is True

        # Delete session
        deleted = await session_manager.delete_session(token)
        assert deleted is True

        # Verify session is gone
        exists = await session_manager.session_exists(token)
        assert exists is False

        # Get should now raise
        with pytest.raises(SessionNotFoundError):
            await session_manager.get_session(token)

    @pytest.mark.asyncio
    async def test_session_expiry(self, redis_client):
        """Test that sessions expire after TTL."""
        # Use very short TTL
        manager = SessionManager(redis_client, ttl=1)
        cookies = {"test": "expiry"}

        token = await manager.store_session(cookies, "https://example.com/")

        # Session should exist immediately
        session = await manager.get_session(token)
        assert session["cookies"] == cookies

        # Wait for expiry
        await asyncio.sleep(1.5)

        # Session should be gone
        with pytest.raises(SessionNotFoundError):
            await manager.get_session(token)

    @pytest.mark.asyncio
    async def test_sliding_window_ttl_refresh(self, redis_client):
        """Test that TTL is refreshed on access."""
        manager = SessionManager(redis_client, ttl=3)
        cookies = {"test": "sliding"}

        token = await manager.store_session(cookies, "https://example.com/")

        # Wait 2 seconds (less than TTL)
        await asyncio.sleep(2)

        # Access session - should refresh TTL
        await manager.get_session(token)

        # Check TTL was refreshed (should be close to 3 again)
        ttl = await manager.get_ttl(token)
        assert ttl > 1  # Should be refreshed, not expired

        # Wait 2 more seconds - session should still exist
        await asyncio.sleep(2)
        session = await manager.get_session(token)
        assert session["cookies"] == cookies

    @pytest.mark.asyncio
    async def test_multiple_concurrent_sessions(self, session_manager):
        """Test multiple sessions can coexist."""
        tokens = []

        # Create multiple sessions
        for i in range(5):
            cookies = {"session": f"session-{i}"}
            token = await session_manager.store_session(
                cookies, f"https://site{i}.example.com/"
            )
            tokens.append(token)

        # All sessions should be retrievable
        for i, token in enumerate(tokens):
            session = await session_manager.get_session(token)
            assert session["cookies"]["session"] == f"session-{i}"

        # Delete specific session
        await session_manager.delete_session(tokens[2])

        # Other sessions should still work
        for i, token in enumerate(tokens):
            if i == 2:
                with pytest.raises(SessionNotFoundError):
                    await session_manager.get_session(token)
            else:
                session = await session_manager.get_session(token)
                assert session is not None


class TestRedisHealthCheck:
    """Integration tests for Redis health checking."""

    @pytest.mark.asyncio
    async def test_redis_ping(self, redis_client):
        """Test that Redis ping works."""
        result = await redis_client.ping()
        assert result is True


class TestSessionData:
    """Integration tests for session data integrity."""

    @pytest.mark.asyncio
    async def test_complex_cookie_data(self, session_manager):
        """Test storing complex cookie data."""
        cookies = {
            "PHPSESSID": "abc123xyz",
            "auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "preferences": "theme=dark;lang=en",
            "tracking": "ga=12345",
        }
        base_url = "https://complex-test.example.com/path/"

        token = await session_manager.store_session(cookies, base_url)
        session = await session_manager.get_session(token)

        assert session["cookies"] == cookies
        assert session["base_url"] == base_url

    @pytest.mark.asyncio
    async def test_unicode_in_session_data(self, session_manager):
        """Test storing unicode characters in session data."""
        cookies = {
            "name": "Test User \u2603",  # Snowman
            "message": "\u4e2d\u6587",  # Chinese characters
        }

        token = await session_manager.store_session(cookies, "https://example.com/")
        session = await session_manager.get_session(token)

        assert session["cookies"] == cookies
