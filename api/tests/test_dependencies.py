"""Tests for FastAPI dependency injection."""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.dependencies import (
    get_current_session,
    get_session_manager,
)
from app.services.session_manager import SessionManager, SessionNotFoundError


class TestGetSessionManager:
    """Tests for get_session_manager dependency."""

    @pytest.mark.asyncio
    async def test_returns_session_manager_instance(self, mock_redis):
        """get_session_manager should return a SessionManager instance."""
        result = await get_session_manager(mock_redis)

        assert isinstance(result, SessionManager)
        assert result.redis == mock_redis


class TestGetCurrentSession:
    """Tests for get_current_session dependency."""

    @pytest.mark.asyncio
    async def test_returns_session_data_for_valid_token(self, mock_session_manager):
        """get_current_session should return session data for valid token."""
        expected_data = {
            "cookies": {"PHPSESSID": "abc123"},
            "base_url": "https://example.com/",
            "created_at": "2024-01-15T10:30:00+00:00",
        }

        # Mock the session manager to return data
        mock_session_manager.get_session = AsyncMock(return_value=expected_data)

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="valid-token-123"
        )

        result = await get_current_session(credentials, mock_session_manager)

        assert result == expected_data
        mock_session_manager.get_session.assert_called_once_with("valid-token-123")

    @pytest.mark.asyncio
    async def test_raises_401_for_invalid_token(self, mock_session_manager):
        """get_current_session should raise 401 for invalid token."""
        mock_session_manager.get_session = AsyncMock(
            side_effect=SessionNotFoundError("Session not found")
        )

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid-token"
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_session(credentials, mock_session_manager)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired session token" in exc_info.value.detail
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    @pytest.mark.asyncio
    async def test_raises_401_for_expired_token(self, mock_session_manager):
        """get_current_session should raise 401 for expired token."""
        mock_session_manager.get_session = AsyncMock(
            side_effect=SessionNotFoundError("Session expired")
        )

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="expired-token"
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_session(credentials, mock_session_manager)

        assert exc_info.value.status_code == 401
