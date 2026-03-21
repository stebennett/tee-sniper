"""Tests for booking API route handlers."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_booking_client, get_session_manager
from app.models.domain import TimeSlot
from app.services.booking_client import BookingClientError, BookingError, LoginError
from app.services.encryption import EncryptionService


@pytest.fixture
def encryption_service(shared_secret: str) -> EncryptionService:
    """Create an EncryptionService for test credential generation."""
    return EncryptionService(shared_secret)


@pytest.fixture
def encrypted_credentials(encryption_service: EncryptionService) -> str:
    """Generate valid encrypted credentials."""
    return encryption_service.encrypt_credentials("testuser", "1234")


@pytest.fixture
def sample_slots() -> list[TimeSlot]:
    """Sample time slots for testing."""
    return [
        TimeSlot(time="08:00", can_book=True, booking_form={"task": "book", "slot": "1"}),
        TimeSlot(time="09:00", can_book=True, booking_form={"task": "book", "slot": "2"}),
        TimeSlot(time="10:00", can_book=False, booking_form={}),
        TimeSlot(time="11:00", can_book=True, booking_form={"task": "book", "slot": "4"}),
        TimeSlot(time="15:00", can_book=True, booking_form={"task": "book", "slot": "5"}),
    ]


@pytest.fixture
def mock_booking_client(sample_slots: list[TimeSlot]) -> AsyncMock:
    """Create a mock BookingClient."""
    client = AsyncMock()
    client.login.return_value = True
    client.get_cookies.return_value = {"session": "abc123"}
    client.get_availability.return_value = sample_slots
    client.book_time_slot.return_value = "booking-123"
    client.add_partner.return_value = True
    return client


@pytest.fixture
def mock_session_manager() -> AsyncMock:
    """Create a mock SessionManager for dependency injection."""
    sm = AsyncMock()
    sm.store_session.return_value = "token-uuid-123"
    sm.ttl = 1800
    return sm


@pytest.fixture
def app_and_client() -> Generator[tuple[FastAPI, TestClient], None, None]:
    """Create an app and test client that share the same instance."""
    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import create_app

    application = create_app()
    with TestClient(application) as client:
        yield application, client

    application.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
def authed_client(
    app_and_client: tuple[FastAPI, TestClient],
    mock_booking_client: AsyncMock,
) -> Generator[TestClient, None, None]:
    """Test client with booking client dependency overridden."""
    application, client = app_and_client

    async def override_booking_client():
        return mock_booking_client

    application.dependency_overrides[get_booking_client] = override_booking_client
    yield client


class TestLoginEndpoint:
    """Tests for POST /api/login."""

    def test_login_success(
        self,
        app_and_client: tuple[FastAPI, TestClient],
        encrypted_credentials: str,
        mock_session_manager: AsyncMock,
    ) -> None:
        application, client = app_and_client
        application.dependency_overrides[get_session_manager] = lambda: mock_session_manager

        with patch("app.routers.booking.BookingClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.login.return_value = True
            mock_instance.get_cookies = MagicMock(return_value={"session": "abc"})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            response = client.post(
                "/api/login",
                json={"credentials": encrypted_credentials},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "expires_at" in data
        assert data["access_token"] == "token-uuid-123"

    def test_login_uses_configured_base_url(
        self,
        app_and_client: tuple[FastAPI, TestClient],
        encrypted_credentials: str,
        mock_session_manager: AsyncMock,
    ) -> None:
        application, client = app_and_client
        application.dependency_overrides[get_session_manager] = lambda: mock_session_manager

        with patch("app.routers.booking.BookingClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.login.return_value = True
            mock_instance.get_cookies = MagicMock(return_value={"session": "abc"})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            response = client.post(
                "/api/login",
                json={"credentials": encrypted_credentials},
            )

            MockClient.assert_called_once_with(
                base_url="https://test-golf-course.example.com/"
            )

        assert response.status_code == 200

    def test_login_ignores_base_url_in_body(
        self,
        app_and_client: tuple[FastAPI, TestClient],
        encrypted_credentials: str,
        mock_session_manager: AsyncMock,
    ) -> None:
        """Verify that base_url in the request body is ignored (SSRF prevention)."""
        application, client = app_and_client
        application.dependency_overrides[get_session_manager] = lambda: mock_session_manager

        with patch("app.routers.booking.BookingClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.login.return_value = True
            mock_instance.get_cookies = MagicMock(return_value={"session": "abc"})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            response = client.post(
                "/api/login",
                json={
                    "credentials": encrypted_credentials,
                    "base_url": "https://evil.example.com/",
                },
            )

            MockClient.assert_called_once_with(
                base_url="https://test-golf-course.example.com/"
            )

        assert response.status_code == 200

    def test_login_encryption_error(
        self,
        app_and_client: tuple[FastAPI, TestClient],
    ) -> None:
        _, client = app_and_client
        response = client.post(
            "/api/login",
            json={"credentials": "invalid-not-base64!!!"},
        )

        assert response.status_code == 400
        assert "Invalid credentials" in response.json()["detail"]

    def test_login_auth_failure(
        self,
        app_and_client: tuple[FastAPI, TestClient],
        encrypted_credentials: str,
        mock_session_manager: AsyncMock,
    ) -> None:
        application, client = app_and_client
        application.dependency_overrides[get_session_manager] = lambda: mock_session_manager

        with patch("app.routers.booking.BookingClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.login.side_effect = LoginError("Invalid credentials")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            response = client.post(
                "/api/login",
                json={"credentials": encrypted_credentials},
            )

        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]

    def test_login_upstream_error(
        self,
        app_and_client: tuple[FastAPI, TestClient],
        encrypted_credentials: str,
        mock_session_manager: AsyncMock,
    ) -> None:
        application, client = app_and_client
        application.dependency_overrides[get_session_manager] = lambda: mock_session_manager

        with patch("app.routers.booking.BookingClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.login.side_effect = BookingClientError("Connection refused")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            response = client.post(
                "/api/login",
                json={"credentials": encrypted_credentials},
            )

        assert response.status_code == 502
        assert "Upstream service error" in response.json()["detail"]

    def test_login_stores_session_with_cookies(
        self,
        app_and_client: tuple[FastAPI, TestClient],
        encrypted_credentials: str,
        mock_session_manager: AsyncMock,
    ) -> None:
        application, client = app_and_client
        application.dependency_overrides[get_session_manager] = lambda: mock_session_manager

        with patch("app.routers.booking.BookingClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.login.return_value = True
            mock_instance.get_cookies = MagicMock(return_value={"PHPSESSID": "xyz789"})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            client.post(
                "/api/login",
                json={"credentials": encrypted_credentials},
            )

        mock_session_manager.store_session.assert_called_once_with(
            {"PHPSESSID": "xyz789"},
            "https://test-golf-course.example.com/",
        )


class TestGetTimesEndpoint:
    """Tests for GET /api/{date}/times."""

    def test_get_times_success(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        response = authed_client.get(
            "/api/2024-01-22/times",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["date"] == "2024-01-22"
        assert data["total_count"] == 5
        assert data["filtered_count"] == 5
        assert len(data["times"]) == 5

    def test_get_times_date_conversion(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        authed_client.get(
            "/api/2024-03-15/times",
            headers={"Authorization": "Bearer test-token"},
        )

        mock_booking_client.get_availability.assert_called_once_with("15-03-2024")

    def test_get_times_start_filter(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        response = authed_client.get(
            "/api/2024-01-22/times?start=09:00",
            headers={"Authorization": "Bearer test-token"},
        )

        data = response.json()
        assert data["total_count"] == 5
        assert data["filtered_count"] == 4
        for t in data["times"]:
            assert t["time"] >= "09:00"

    def test_get_times_end_filter(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        response = authed_client.get(
            "/api/2024-01-22/times?end=10:00",
            headers={"Authorization": "Bearer test-token"},
        )

        data = response.json()
        assert data["total_count"] == 5
        assert data["filtered_count"] == 3
        for t in data["times"]:
            assert t["time"] <= "10:00"

    def test_get_times_combined_filters(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        response = authed_client.get(
            "/api/2024-01-22/times?start=09:00&end=11:00",
            headers={"Authorization": "Bearer test-token"},
        )

        data = response.json()
        assert data["total_count"] == 5
        assert data["filtered_count"] == 3
        for t in data["times"]:
            assert "09:00" <= t["time"] <= "11:00"

    def test_get_times_upstream_error(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        mock_booking_client.get_availability.side_effect = BookingClientError(
            "Connection refused"
        )

        response = authed_client.get(
            "/api/2024-01-22/times",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 502
        assert "Upstream service error" in response.json()["detail"]

    def test_get_times_total_vs_filtered_counts(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        """Verify total_count reflects pre-filter and filtered_count reflects post-filter."""
        response = authed_client.get(
            "/api/2024-01-22/times?start=10:00&end=11:00",
            headers={"Authorization": "Bearer test-token"},
        )

        data = response.json()
        assert data["total_count"] == 5
        assert data["filtered_count"] == 2

    def test_get_times_includes_booking_form(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        response = authed_client.get(
            "/api/2024-01-22/times",
            headers={"Authorization": "Bearer test-token"},
        )

        data = response.json()
        bookable_slot = data["times"][0]
        assert bookable_slot["booking_form"] == {"task": "book", "slot": "1"}


class TestBookTimeEndpoint:
    """Tests for POST /api/{date}/time/{time}/book."""

    def test_book_success(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        response = authed_client.post(
            "/api/2024-01-22/time/09:00/book",
            headers={"Authorization": "Bearer test-token"},
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["booking_id"] == "booking-123"
        assert data["date"] == "2024-01-22"
        assert data["time"] == "09:00"
        assert data["slots_booked"] == 1

    def test_book_dry_run(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        response = authed_client.post(
            "/api/2024-01-22/time/09:00/book",
            headers={"Authorization": "Bearer test-token"},
            json={"dry_run": True},
        )

        assert response.status_code == 200
        mock_booking_client.book_time_slot.assert_called_once()
        call_args = mock_booking_client.book_time_slot.call_args
        assert call_args[0][2] is True  # dry_run=True

    def test_book_custom_num_slots(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        response = authed_client.post(
            "/api/2024-01-22/time/09:00/book",
            headers={"Authorization": "Bearer test-token"},
            json={"num_slots": 3},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["slots_booked"] == 3
        call_args = mock_booking_client.book_time_slot.call_args
        assert call_args[0][1] == 3  # num_slots=3

    def test_book_slot_not_found(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        response = authed_client.post(
            "/api/2024-01-22/time/12:00/book",
            headers={"Authorization": "Bearer test-token"},
            json={},
        )

        assert response.status_code == 404
        assert "No bookable slot found" in response.json()["detail"]

    def test_book_unbookable_slot_not_found(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        """Slot exists at 10:00 but can_book=False, so should return 404."""
        response = authed_client.post(
            "/api/2024-01-22/time/10:00/book",
            headers={"Authorization": "Bearer test-token"},
            json={},
        )

        assert response.status_code == 404

    def test_book_booking_error(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        mock_booking_client.book_time_slot.side_effect = BookingError("Slot taken")

        response = authed_client.post(
            "/api/2024-01-22/time/09:00/book",
            headers={"Authorization": "Bearer test-token"},
            json={},
        )

        assert response.status_code == 422
        assert "Slot taken" in response.json()["detail"]

    def test_book_upstream_error(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        mock_booking_client.book_time_slot.side_effect = BookingClientError(
            "Connection lost"
        )

        response = authed_client.post(
            "/api/2024-01-22/time/09:00/book",
            headers={"Authorization": "Bearer test-token"},
            json={},
        )

        assert response.status_code == 502
        assert "Upstream service error" in response.json()["detail"]

    def test_book_date_conversion(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        authed_client.post(
            "/api/2024-06-01/time/09:00/book",
            headers={"Authorization": "Bearer test-token"},
            json={},
        )

        mock_booking_client.get_availability.assert_called_once_with("01-06-2024")


class TestAddPartnersEndpoint:
    """Tests for PATCH /api/bookings/{booking_id}."""

    def test_add_partners_full_success(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        response = authed_client.patch(
            "/api/bookings/booking-123",
            headers={"Authorization": "Bearer test-token"},
            json={"partners": ["P001", "P002"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["booking_id"] == "booking-123"
        assert data["partners_added"] == ["P001", "P002"]
        assert data["partners_failed"] == []
        assert "All partners added successfully" in data["message"]

    def test_add_partners_partial_failure(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        mock_booking_client.add_partner.side_effect = [
            True,
            BookingClientError("Partner not found"),
        ]

        response = authed_client.patch(
            "/api/bookings/booking-123",
            headers={"Authorization": "Bearer test-token"},
            json={"partners": ["P001", "P002"]},
        )

        assert response.status_code == 207
        data = response.json()
        assert data["partners_added"] == ["P001"]
        assert data["partners_failed"] == ["P002"]

    def test_add_partners_total_failure(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        mock_booking_client.add_partner.side_effect = BookingClientError("Failed")

        response = authed_client.patch(
            "/api/bookings/booking-123",
            headers={"Authorization": "Bearer test-token"},
            json={"partners": ["P001", "P002"]},
        )

        assert response.status_code == 502
        assert "Failed to add any partners" in response.json()["detail"]

    def test_add_partners_correct_slot_numbering(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        authed_client.patch(
            "/api/bookings/booking-123",
            headers={"Authorization": "Bearer test-token"},
            json={"partners": ["P001", "P002", "P003"]},
        )

        calls = mock_booking_client.add_partner.call_args_list
        assert len(calls) == 3
        assert calls[0][0] == ("booking-123", "P001", 2, False)
        assert calls[1][0] == ("booking-123", "P002", 3, False)
        assert calls[2][0] == ("booking-123", "P003", 4, False)

    def test_add_partners_dry_run(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        authed_client.patch(
            "/api/bookings/booking-123",
            headers={"Authorization": "Bearer test-token"},
            json={"partners": ["P001"], "dry_run": True},
        )

        call_args = mock_booking_client.add_partner.call_args
        assert call_args[0] == ("booking-123", "P001", 2, True)

    def test_add_partners_empty_list_rejected(
        self,
        authed_client: TestClient,
    ) -> None:
        response = authed_client.patch(
            "/api/bookings/booking-123",
            headers={"Authorization": "Bearer test-token"},
            json={"partners": []},
        )

        assert response.status_code == 422

    def test_add_partners_too_many_rejected(
        self,
        authed_client: TestClient,
    ) -> None:
        response = authed_client.patch(
            "/api/bookings/booking-123",
            headers={"Authorization": "Bearer test-token"},
            json={"partners": ["P1", "P2", "P3", "P4"]},
        )

        assert response.status_code == 422

    def test_add_partners_single_partner(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        response = authed_client.patch(
            "/api/bookings/booking-123",
            headers={"Authorization": "Bearer test-token"},
            json={"partners": ["P001"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["partners_added"] == ["P001"]
        assert data["partners_failed"] == []


class TestDateValidation:
    """Tests for date path parameter validation."""

    def test_date_conversion_via_endpoint(
        self,
        authed_client: TestClient,
        mock_booking_client: AsyncMock,
    ) -> None:
        """Verify date is correctly converted from YYYY-MM-DD to DD-MM-YYYY."""
        authed_client.get(
            "/api/2024-03-05/times",
            headers={"Authorization": "Bearer test-token"},
        )
        mock_booking_client.get_availability.assert_called_once_with("05-03-2024")

    def test_invalid_date_returns_422(
        self,
        authed_client: TestClient,
    ) -> None:
        response = authed_client.get(
            "/api/not-a-date/times",
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 422

    def test_invalid_date_format_returns_422(
        self,
        authed_client: TestClient,
    ) -> None:
        response = authed_client.get(
            "/api/22-01-2024/times",
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 422


class TestTimeFilterValidation:
    """Tests for time filter query parameter validation."""

    def test_invalid_start_time_returns_422(
        self,
        authed_client: TestClient,
    ) -> None:
        response = authed_client.get(
            "/api/2024-01-22/times?start=9am",
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 422

    def test_invalid_end_time_returns_422(
        self,
        authed_client: TestClient,
    ) -> None:
        response = authed_client.get(
            "/api/2024-01-22/times?end=25:00:00",
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 422
