"""Booking client service for golf course website interaction."""

import httpx

from app.models.domain import TimeSlot
from app.utils.html_parser import (
    extract_booking_id,
    parse_availability,
    parse_booking_response,
    parse_login_response,
)
from app.utils.user_agents import get_random_user_agent


class BookingClientError(Exception):
    """Base exception for booking client errors."""

    pass


class LoginError(BookingClientError):
    """Raised when login fails."""

    pass


class BookingError(BookingClientError):
    """Raised when booking fails."""

    pass


class BookingClient:
    """Async client for interacting with golf course booking website.

    Mirrors the Go implementation in pkg/clients/bookingclient.go.
    Uses httpx for async HTTP requests and maintains session cookies.
    """

    # Headers matching Go implementation
    DEFAULT_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self, base_url: str, cookies: dict[str, str] | None = None):
        """Initialize booking client.

        Args:
            base_url: Base URL of the booking website (trailing slash stripped)
            cookies: Optional existing session cookies to restore
        """
        self.base_url = base_url.rstrip("/")
        self._user_agent = get_random_user_agent()
        self._client: httpx.AsyncClient | None = None
        self._initial_cookies = cookies or {}

    async def __aenter__(self) -> "BookingClient":
        """Async context manager entry - ensures client is initialized."""
        await self._ensure_client()
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit - closes the client."""
        await self.close()

    async def _ensure_client(self) -> None:
        """Lazily initialize the HTTP client if needed."""
        if self._client is None:
            headers = {**self.DEFAULT_HEADERS, "User-Agent": self._user_agent}
            self._client = httpx.AsyncClient(
                headers=headers,
                cookies=self._initial_cookies,
                follow_redirects=True,
                timeout=30.0,
            )

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def login(self, username: str, pin: str) -> bool:
        """Login to booking site.

        Returns True on successful authentication, False on auth failure.
        Raises BookingClientError on network/HTTP errors.

        Mirrors Go: Login(username, password string) (bool, error)
        """
        await self._ensure_client()

        form_data = {
            "task": "login",
            "topmenu": "1",
            "memberid": username,
            "pin": pin,
            "cachemid": "1",
            "Submit": "Login",
        }

        resp = await self._client.post(
            f"{self.base_url}/login.php",
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()

        return parse_login_response(resp.text)

    async def get_availability(self, date: str) -> list[TimeSlot]:
        """Get available tee times for a date.

        Args:
            date: Date string in DD-MM-YYYY format

        Returns:
            List of bookable TimeSlot objects

        Mirrors Go: GetCourseAvailability(dateStr string) ([]models.TimeSlot, error)
        """
        await self._ensure_client()

        resp = await self._client.get(
            f"{self.base_url}/memberbooking/",
            params={"date": date},
        )
        resp.raise_for_status()

        return parse_availability(resp.text)

    async def book_time_slot(
        self, time_slot: TimeSlot, num_slots: int = 1, dry_run: bool = False
    ) -> str:
        """Book a time slot.

        Args:
            time_slot: The TimeSlot to book (must be bookable)
            num_slots: Number of slots to book (1-4, includes main player)
            dry_run: If True, simulates booking without making actual request

        Returns:
            Booking ID string on success

        Raises:
            BookingError on failure

        Mirrors Go: BookTimeSlot(timeSlot models.TimeSlot, playingPartners []string, dryRun bool)
        """
        await self._ensure_client()

        if not time_slot.can_book:
            raise BookingError("Time slot is not bookable")

        if not 1 <= num_slots <= 4:
            raise BookingError("num_slots must be between 1 and 4")

        # Dry run returns simulated booking ID
        if dry_run:
            return "dryrun-booking-id"

        # Combine form params with num_slots
        params = {**time_slot.booking_form, "numslots": str(num_slots)}

        resp = await self._client.get(
            f"{self.base_url}/memberbooking/",
            params=params,
        )
        resp.raise_for_status()

        success, error = parse_booking_response(resp.text)
        if not success:
            raise BookingError(error)

        # Extract booking ID from response URL (after redirects)
        booking_id = extract_booking_id(str(resp.url))
        if not booking_id:
            raise BookingError("Could not extract booking ID from response")

        return booking_id

    async def add_partner(
        self, booking_id: str, partner_id: str, slot_num: int, dry_run: bool = False
    ) -> bool:
        """Add a playing partner to an existing booking.

        Args:
            booking_id: The booking ID from book_time_slot()
            partner_id: The partner's member ID
            slot_num: Slot number (2, 3, or 4 - slot 1 is the main player)
            dry_run: If True, simulates without making actual request

        Returns:
            True on success

        Raises:
            BookingError on invalid slot_num

        Mirrors Go: AddPlayingPartner(bookingID, partnerID string, slotNumber int, dryRun bool)
        """
        await self._ensure_client()

        if not 2 <= slot_num <= 4:
            raise BookingError("slot_num must be between 2 and 4")

        # Dry run returns success
        if dry_run:
            return True

        resp = await self._client.get(
            f"{self.base_url}/memberbooking/",
            params={
                "edit": booking_id,
                "addpartner": partner_id,
                "partnerslot": str(slot_num),
            },
        )

        return resp.status_code == 200

    def get_cookies(self) -> dict[str, str]:
        """Return current session cookies for storage/restoration.

        Returns:
            Dictionary of cookie name -> value
        """
        if self._client:
            return dict(self._client.cookies)
        return {}
