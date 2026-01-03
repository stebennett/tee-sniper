"""Tests for health check endpoint."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self, test_client: TestClient) -> None:
        """Test that health endpoint returns 200 OK."""
        response = test_client.get("/health")

        assert response.status_code == 200

    def test_health_includes_status(self, test_client: TestClient) -> None:
        """Test that health endpoint returns a status field."""
        response = test_client.get("/health")
        data = response.json()

        # Status is either "healthy" (Redis available) or "degraded" (Redis unavailable)
        assert data["status"] in ["healthy", "degraded"]

    def test_health_includes_timestamp(self, test_client: TestClient) -> None:
        """Test that health response includes timestamp."""
        response = test_client.get("/health")
        data = response.json()

        assert "timestamp" in data
        # Timestamp should be ISO format
        assert "T" in data["timestamp"]

    def test_health_includes_redis_connected(self, test_client: TestClient) -> None:
        """Test that health response includes redis_connected field."""
        response = test_client.get("/health")
        data = response.json()

        assert "redis_connected" in data
        assert isinstance(data["redis_connected"], bool)

    def test_health_status_matches_redis_connection(
        self, test_client: TestClient
    ) -> None:
        """Test that status reflects Redis connection state."""
        response = test_client.get("/health")
        data = response.json()

        if data["redis_connected"]:
            assert data["status"] == "healthy"
        else:
            assert data["status"] == "degraded"
