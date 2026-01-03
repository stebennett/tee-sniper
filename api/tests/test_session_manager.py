"""Unit tests for SessionManager service."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.services.session_manager import (
    SessionManager,
    SessionNotFoundError,
)


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock()
    return redis


@pytest.fixture
def session_manager(mock_redis):
    """Create a SessionManager with mock Redis."""
    return SessionManager(mock_redis, ttl=1800)


class TestStoreSession:
    """Tests for store_session method."""

    @pytest.mark.asyncio
    async def test_store_session_returns_uuid_token(self, session_manager):
        """store_session should return a valid UUID token."""
        cookies = {"PHPSESSID": "abc123"}
        base_url = "https://example.com/"

        token = await session_manager.store_session(cookies, base_url)

        # Verify it's a valid UUID format
        assert len(token) == 36
        assert token.count("-") == 4

    @pytest.mark.asyncio
    async def test_store_session_saves_correct_data(self, session_manager, mock_redis):
        """store_session should save cookies and base_url to Redis."""
        cookies = {"PHPSESSID": "abc123", "other": "value"}
        base_url = "https://example.com/"

        token = await session_manager.store_session(cookies, base_url)

        # Verify setex was called with correct arguments
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args

        # Check key format
        assert call_args[0][0] == f"session:{token}"
        # Check TTL
        assert call_args[0][1] == 1800

        # Check stored data
        stored_data = json.loads(call_args[0][2])
        assert stored_data["cookies"] == cookies
        assert stored_data["base_url"] == base_url
        assert "created_at" in stored_data

    @pytest.mark.asyncio
    async def test_store_session_uses_custom_ttl(self, mock_redis):
        """store_session should use the configured TTL."""
        manager = SessionManager(mock_redis, ttl=3600)
        cookies = {"PHPSESSID": "abc123"}

        await manager.store_session(cookies, "https://example.com/")

        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 3600


class TestGetSession:
    """Tests for get_session method."""

    @pytest.mark.asyncio
    async def test_get_session_returns_stored_data(self, session_manager, mock_redis):
        """get_session should return the stored session data."""
        expected_data = {
            "cookies": {"PHPSESSID": "abc123"},
            "base_url": "https://example.com/",
            "created_at": "2024-01-15T10:30:00+00:00",
        }
        mock_redis.get.return_value = json.dumps(expected_data)

        result = await session_manager.get_session("test-token-123")

        assert result == expected_data
        mock_redis.get.assert_called_once_with("session:test-token-123")

    @pytest.mark.asyncio
    async def test_get_session_refreshes_ttl(self, session_manager, mock_redis):
        """get_session should refresh TTL on access (sliding window)."""
        mock_redis.get.return_value = json.dumps({"cookies": {}, "base_url": ""})

        await session_manager.get_session("test-token-123")

        mock_redis.expire.assert_called_once_with("session:test-token-123", 1800)

    @pytest.mark.asyncio
    async def test_get_session_raises_not_found_for_invalid_token(
        self, session_manager, mock_redis
    ):
        """get_session should raise SessionNotFoundError for invalid token."""
        mock_redis.get.return_value = None

        with pytest.raises(SessionNotFoundError) as exc_info:
            await session_manager.get_session("invalid-token")

        assert "not found or expired" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_session_raises_not_found_for_expired_session(
        self, session_manager, mock_redis
    ):
        """get_session should raise SessionNotFoundError for expired session."""
        mock_redis.get.return_value = None

        with pytest.raises(SessionNotFoundError):
            await session_manager.get_session("expired-token")


class TestDeleteSession:
    """Tests for delete_session method."""

    @pytest.mark.asyncio
    async def test_delete_session_removes_session(self, session_manager, mock_redis):
        """delete_session should remove the session from Redis."""
        mock_redis.delete.return_value = 1

        result = await session_manager.delete_session("test-token-123")

        assert result is True
        mock_redis.delete.assert_called_once_with("session:test-token-123")

    @pytest.mark.asyncio
    async def test_delete_session_returns_false_for_nonexistent(
        self, session_manager, mock_redis
    ):
        """delete_session should return False for non-existent session."""
        mock_redis.delete.return_value = 0

        result = await session_manager.delete_session("nonexistent-token")

        assert result is False


class TestSessionExists:
    """Tests for session_exists method."""

    @pytest.mark.asyncio
    async def test_session_exists_returns_true_for_valid(
        self, session_manager, mock_redis
    ):
        """session_exists should return True for existing session."""
        mock_redis.exists.return_value = 1

        result = await session_manager.session_exists("valid-token")

        assert result is True
        mock_redis.exists.assert_called_once_with("session:valid-token")

    @pytest.mark.asyncio
    async def test_session_exists_returns_false_for_invalid(
        self, session_manager, mock_redis
    ):
        """session_exists should return False for non-existent session."""
        mock_redis.exists.return_value = 0

        result = await session_manager.session_exists("invalid-token")

        assert result is False


class TestGetTTL:
    """Tests for get_ttl method."""

    @pytest.mark.asyncio
    async def test_get_ttl_returns_remaining_time(self, session_manager, mock_redis):
        """get_ttl should return remaining TTL in seconds."""
        mock_redis.ttl.return_value = 1500

        result = await session_manager.get_ttl("test-token")

        assert result == 1500
        mock_redis.ttl.assert_called_once_with("session:test-token")

    @pytest.mark.asyncio
    async def test_get_ttl_returns_negative_for_nonexistent(
        self, session_manager, mock_redis
    ):
        """get_ttl should return -2 for non-existent key."""
        mock_redis.ttl.return_value = -2

        result = await session_manager.get_ttl("nonexistent-token")

        assert result == -2


class TestKeyGeneration:
    """Tests for Redis key generation."""

    def test_key_prefix(self, session_manager):
        """Keys should use correct prefix format."""
        key = session_manager._key("my-token")
        assert key == "session:my-token"

    def test_default_ttl(self, mock_redis):
        """Default TTL should be 30 minutes (1800 seconds)."""
        manager = SessionManager(mock_redis)
        assert manager.ttl == 1800
