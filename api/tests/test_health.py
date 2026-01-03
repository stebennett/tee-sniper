"""Tests for health check endpoint."""

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_returns_200(self, test_client: TestClient) -> None:
        """Test that health endpoint returns 200 OK."""
        response = test_client.get("/health")

        assert response.status_code == 200

    def test_health_returns_healthy_status(self, test_client: TestClient) -> None:
        """Test that health endpoint returns healthy status."""
        response = test_client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"

    def test_health_includes_timestamp(self, test_client: TestClient) -> None:
        """Test that health response includes timestamp."""
        response = test_client.get("/health")
        data = response.json()

        assert "timestamp" in data
        # Timestamp should be ISO format
        assert "T" in data["timestamp"]
