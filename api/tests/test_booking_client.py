"""Tests for BookingClient service."""

import re
from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from app.models.domain import TimeSlot
from app.services.booking_client import (
    BookingClient,
    BookingError,
)
from app.utils.user_agents import USER_AGENTS

# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> str:
    """Load HTML fixture file content."""
    return (FIXTURES_DIR / filename).read_text()


@pytest.fixture
def base_url() -> str:
    """Base URL for booking site."""
    return "https://booking.example.com"


@pytest.fixture
def sample_time_slot() -> TimeSlot:
    """Sample bookable time slot."""
    return TimeSlot(
        time="09:00",
        can_book=True,
        booking_form={
            "date": "2024-01-15",
            "time": "0900",
            "course": "1",
            "holes": "18",
        },
    )


class TestBookingClientInit:
    """Tests for BookingClient initialization."""

    def test_strips_trailing_slash(self, base_url: str):
        """Base URL trailing slash is stripped."""
        client = BookingClient(base_url + "/")
        assert client.base_url == base_url

    def test_user_agent_selected(self, base_url: str):
        """A valid user agent is selected on init."""
        client = BookingClient(base_url)
        assert client._user_agent in USER_AGENTS

    def test_initial_cookies_stored(self, base_url: str):
        """Initial cookies are stored for later use."""
        cookies = {"session": "abc123"}
        client = BookingClient(base_url, cookies=cookies)
        assert client._initial_cookies == cookies


class TestBookingClientContextManager:
    """Tests for async context manager behavior."""

    @pytest.mark.asyncio
    async def test_context_manager_creates_client(self, base_url: str):
        """Entering context creates HTTP client."""
        async with BookingClient(base_url) as client:
            assert client._client is not None

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self, base_url: str):
        """Exiting context closes HTTP client."""
        client = BookingClient(base_url)
        async with client:
            pass
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_without_client(self, base_url: str):
        """Closing without client doesn't error."""
        client = BookingClient(base_url)
        await client.close()  # Should not raise


class TestBookingClientLogin:
    """Tests for login method."""

    @pytest.mark.asyncio
    async def test_login_success(self, httpx_mock: HTTPXMock, base_url: str):
        """Successful login returns True."""
        httpx_mock.add_response(
            url=f"{base_url}/login.php",
            method="POST",
            html=load_fixture("login_success.html"),
        )

        async with BookingClient(base_url) as client:
            result = await client.login("testuser", "1234")

        assert result is True

    @pytest.mark.asyncio
    async def test_login_failure(self, httpx_mock: HTTPXMock, base_url: str):
        """Failed login returns False."""
        httpx_mock.add_response(
            url=f"{base_url}/login.php",
            method="POST",
            html=load_fixture("login_failure.html"),
        )

        async with BookingClient(base_url) as client:
            result = await client.login("testuser", "wrong")

        assert result is False

    @pytest.mark.asyncio
    async def test_login_sends_correct_form_data(
        self, httpx_mock: HTTPXMock, base_url: str
    ):
        """Login sends expected form parameters."""
        httpx_mock.add_response(
            url=f"{base_url}/login.php",
            method="POST",
            html=load_fixture("login_success.html"),
        )

        async with BookingClient(base_url) as client:
            await client.login("testuser", "1234")

        request = httpx_mock.get_request()
        assert request is not None
        content = request.content.decode()
        assert "memberid=testuser" in content
        assert "pin=1234" in content
        assert "task=login" in content
        assert "Submit=Login" in content


class TestBookingClientGetAvailability:
    """Tests for get_availability method."""

    @pytest.mark.asyncio
    async def test_returns_available_slots(self, httpx_mock: HTTPXMock, base_url: str):
        """Returns list of bookable time slots."""
        httpx_mock.add_response(
            url=re.compile(rf"{re.escape(base_url)}/memberbooking/.*"),
            method="GET",
            html=load_fixture("availability_with_slots.html"),
        )

        async with BookingClient(base_url) as client:
            slots = await client.get_availability("15-01-2024")

        assert len(slots) == 3
        assert slots[0].time == "09:00"
        assert slots[0].can_book is True

    @pytest.mark.asyncio
    async def test_sends_date_param(self, httpx_mock: HTTPXMock, base_url: str):
        """Date is passed as query parameter."""
        httpx_mock.add_response(
            url=re.compile(rf"{re.escape(base_url)}/memberbooking/.*"),
            method="GET",
            html=load_fixture("availability_empty.html"),
        )

        async with BookingClient(base_url) as client:
            await client.get_availability("15-01-2024")

        request = httpx_mock.get_request()
        assert request is not None
        assert "date=15-01-2024" in str(request.url)

    @pytest.mark.asyncio
    async def test_empty_availability(self, httpx_mock: HTTPXMock, base_url: str):
        """Returns empty list when no slots available."""
        httpx_mock.add_response(
            url=re.compile(rf"{re.escape(base_url)}/memberbooking/.*"),
            method="GET",
            html=load_fixture("availability_empty.html"),
        )

        async with BookingClient(base_url) as client:
            slots = await client.get_availability("15-01-2024")

        assert len(slots) == 0


class TestBookingClientBookTimeSlot:
    """Tests for book_time_slot method."""

    @pytest.mark.asyncio
    async def test_booking_success_with_edit_param(
        self,
        httpx_mock: HTTPXMock,
        base_url: str,
        sample_time_slot: TimeSlot,
    ):
        """Successful booking returns booking ID when edit param is in URL."""
        # Simulate a request that includes the edit param (e.g., after a redirect)
        # by making the booking request URL itself contain edit param
        httpx_mock.add_response(
            url=re.compile(rf"{re.escape(base_url)}/memberbooking/.*edit=BOOK123.*"),
            method="GET",
            html=load_fixture("booking_success.html"),
        )

        # Modify sample slot to include edit param (simulating redirect behavior)
        slot_with_edit = TimeSlot(
            time=sample_time_slot.time,
            can_book=True,
            booking_form={**sample_time_slot.booking_form, "edit": "BOOK123"},
        )

        async with BookingClient(base_url) as client:
            booking_id = await client.book_time_slot(slot_with_edit, num_slots=2)

        assert booking_id == "BOOK123"

    @pytest.mark.asyncio
    async def test_booking_success_extracts_id_from_redirect(
        self,
        base_url: str,
        sample_time_slot: TimeSlot,
    ):
        """Booking extracts ID from response URL after redirect."""
        # This tests the actual redirect scenario using a mock transport
        # that properly simulates the redirect URL
        from unittest.mock import AsyncMock, patch

        redirect_url = f"{base_url}/memberbooking/?edit=BOOK123&confirmed=1"

        async with BookingClient(base_url) as client:
            # Create a mock response with the redirect URL
            mock_response = httpx.Response(
                200,
                content=load_fixture("booking_success.html").encode(),
                request=httpx.Request("GET", redirect_url),
            )

            # Patch the client's get method to return our mock
            with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_response
                booking_id = await client.book_time_slot(sample_time_slot, num_slots=2)

        assert booking_id == "BOOK123"

    @pytest.mark.asyncio
    async def test_booking_failure(
        self,
        httpx_mock: HTTPXMock,
        base_url: str,
        sample_time_slot: TimeSlot,
    ):
        """Failed booking raises BookingError."""
        httpx_mock.add_response(
            url=re.compile(rf"{re.escape(base_url)}/memberbooking/.*"),
            method="GET",
            html=load_fixture("booking_failure.html"),
        )

        async with BookingClient(base_url) as client:
            with pytest.raises(BookingError):
                await client.book_time_slot(sample_time_slot)

    @pytest.mark.asyncio
    async def test_unbookable_slot_raises_error(self, base_url: str):
        """Trying to book unbookable slot raises error."""
        unbookable_slot = TimeSlot(
            time="09:00",
            can_book=False,
            booking_form={},
        )

        async with BookingClient(base_url) as client:
            with pytest.raises(BookingError, match="not bookable"):
                await client.book_time_slot(unbookable_slot)

    @pytest.mark.asyncio
    async def test_invalid_num_slots_raises_error(
        self, base_url: str, sample_time_slot: TimeSlot
    ):
        """Invalid num_slots raises error."""
        async with BookingClient(base_url) as client:
            with pytest.raises(BookingError, match="between 1 and 4"):
                await client.book_time_slot(sample_time_slot, num_slots=0)

            with pytest.raises(BookingError, match="between 1 and 4"):
                await client.book_time_slot(sample_time_slot, num_slots=5)

    @pytest.mark.asyncio
    async def test_dry_run_returns_mock_id(
        self, base_url: str, sample_time_slot: TimeSlot
    ):
        """Dry run returns simulated booking ID without HTTP request."""
        async with BookingClient(base_url) as client:
            booking_id = await client.book_time_slot(
                sample_time_slot, num_slots=1, dry_run=True
            )

        assert booking_id == "dryrun-booking-id"

    @pytest.mark.asyncio
    async def test_sends_form_params(
        self,
        base_url: str,
        sample_time_slot: TimeSlot,
    ):
        """Booking sends form parameters and numslots."""
        from unittest.mock import AsyncMock, patch

        redirect_url = f"{base_url}/memberbooking/?edit=BOOK123"
        captured_url = None

        async def capture_get(*args, **kwargs):
            nonlocal captured_url
            captured_url = kwargs.get("params", {})
            return httpx.Response(
                200,
                content=load_fixture("booking_success.html").encode(),
                request=httpx.Request("GET", redirect_url),
            )

        async with BookingClient(base_url) as client:
            with patch.object(client._client, "get", side_effect=capture_get):
                await client.book_time_slot(sample_time_slot, num_slots=3)

        # Verify form params and numslots were sent
        assert captured_url is not None
        assert captured_url.get("date") == "2024-01-15"
        assert captured_url.get("time") == "0900"
        assert captured_url.get("numslots") == "3"


class TestBookingClientAddPartner:
    """Tests for add_partner method."""

    @pytest.mark.asyncio
    async def test_add_partner_success(self, httpx_mock: HTTPXMock, base_url: str):
        """Successful partner addition returns True."""
        httpx_mock.add_response(
            url=re.compile(rf"{re.escape(base_url)}/memberbooking/.*"),
            method="GET",
            status_code=200,
        )

        async with BookingClient(base_url) as client:
            result = await client.add_partner("BOOK123", "PARTNER456", slot_num=2)

        assert result is True

    @pytest.mark.asyncio
    async def test_add_partner_sends_correct_params(
        self, httpx_mock: HTTPXMock, base_url: str
    ):
        """Partner addition sends correct query parameters."""
        httpx_mock.add_response(
            url=re.compile(rf"{re.escape(base_url)}/memberbooking/.*"),
            method="GET",
            status_code=200,
        )

        async with BookingClient(base_url) as client:
            await client.add_partner("BOOK123", "PARTNER456", slot_num=3)

        request = httpx_mock.get_request()
        assert request is not None
        url_str = str(request.url)
        assert "edit=BOOK123" in url_str
        assert "addpartner=PARTNER456" in url_str
        assert "partnerslot=3" in url_str

    @pytest.mark.asyncio
    async def test_invalid_slot_num_raises_error(self, base_url: str):
        """Invalid slot_num raises error."""
        async with BookingClient(base_url) as client:
            with pytest.raises(BookingError, match="between 2 and 4"):
                await client.add_partner("BOOK123", "PARTNER456", slot_num=1)

            with pytest.raises(BookingError, match="between 2 and 4"):
                await client.add_partner("BOOK123", "PARTNER456", slot_num=5)

    @pytest.mark.asyncio
    async def test_dry_run_returns_true(self, base_url: str):
        """Dry run returns True without HTTP request."""
        async with BookingClient(base_url) as client:
            result = await client.add_partner(
                "BOOK123", "PARTNER456", slot_num=2, dry_run=True
            )

        assert result is True


class TestBookingClientCookies:
    """Tests for cookie handling."""

    @pytest.mark.asyncio
    async def test_get_cookies_returns_session_cookies(
        self, httpx_mock: HTTPXMock, base_url: str
    ):
        """get_cookies returns cookies from session."""
        httpx_mock.add_response(
            url=f"{base_url}/login.php",
            method="POST",
            html=load_fixture("login_success.html"),
            headers={"Set-Cookie": "session=xyz789; Path=/"},
        )

        async with BookingClient(base_url) as client:
            await client.login("user", "pass")
            cookies = client.get_cookies()

        assert "session" in cookies
        assert cookies["session"] == "xyz789"

    @pytest.mark.asyncio
    async def test_initial_cookies_used(self, httpx_mock: HTTPXMock, base_url: str):
        """Initial cookies are sent with requests."""
        httpx_mock.add_response(
            url=re.compile(rf"{re.escape(base_url)}/memberbooking/.*"),
            method="GET",
            html=load_fixture("availability_empty.html"),
        )

        initial_cookies = {"session": "existing123"}
        async with BookingClient(base_url, cookies=initial_cookies) as client:
            await client.get_availability("15-01-2024")

        request = httpx_mock.get_request()
        assert request is not None
        assert "session=existing123" in request.headers.get("cookie", "")

    def test_get_cookies_without_client(self, base_url: str):
        """get_cookies returns empty dict when client not initialized."""
        client = BookingClient(base_url)
        assert client.get_cookies() == {}


class TestBookingClientHeaders:
    """Tests for HTTP headers."""

    @pytest.mark.asyncio
    async def test_browser_headers_set(self, httpx_mock: HTTPXMock, base_url: str):
        """Browser-like headers are set on requests."""
        httpx_mock.add_response(
            url=re.compile(rf"{re.escape(base_url)}/memberbooking/.*"),
            method="GET",
            html=load_fixture("availability_empty.html"),
        )

        async with BookingClient(base_url) as client:
            await client.get_availability("15-01-2024")

        request = httpx_mock.get_request()
        assert request is not None
        assert "Mozilla" in request.headers.get("user-agent", "")
        assert "text/html" in request.headers.get("accept", "")

    @pytest.mark.asyncio
    async def test_user_agent_from_list(self, base_url: str):
        """User agent is selected from predefined list."""
        client = BookingClient(base_url)
        assert client._user_agent in USER_AGENTS


class TestUserAgentRandomization:
    """Tests for user agent randomization."""

    def test_random_user_agent_selection(self, base_url: str):
        """Different clients may get different user agents."""
        # Create multiple clients and check we get variety
        # (with 5 user agents, probability of all same after 20 tries is very low)
        user_agents = set()
        for _ in range(20):
            client = BookingClient(base_url)
            user_agents.add(client._user_agent)

        # Should have at least 2 different user agents
        assert len(user_agents) >= 2
