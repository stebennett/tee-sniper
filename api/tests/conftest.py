"""Pytest fixtures and configuration."""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def set_test_env() -> Generator[None, None, None]:
    """Set required environment variables for testing."""
    original_env = os.environ.copy()

    # Set test environment variables
    os.environ["TSA_SHARED_SECRET"] = "test-shared-secret-for-testing"
    os.environ["TSA_REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["TSA_BASE_URL"] = "https://test-golf-course.example.com/"
    os.environ["TSA_LOG_LEVEL"] = "DEBUG"
    os.environ["TSA_LOG_FORMAT"] = "text"

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def test_client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    # Clear settings cache before creating app
    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        yield client

    # Clear cache after test
    get_settings.cache_clear()


@pytest.fixture
def shared_secret() -> str:
    """Test shared secret for encryption tests."""
    return "test-shared-secret-for-testing"
