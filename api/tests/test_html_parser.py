"""Tests for HTML parsing utilities."""

from pathlib import Path

import pytest

from app.utils.html_parser import (
    extract_booking_id,
    parse_availability,
    parse_booking_response,
    parse_login_response,
)

# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> str:
    """Load HTML fixture file content."""
    return (FIXTURES_DIR / filename).read_text()


class TestParseLoginResponse:
    """Tests for parse_login_response function."""

    def test_login_success(self):
        """Title starting with 'Welcome' indicates success."""
        html = load_fixture("login_success.html")
        assert parse_login_response(html) is True

    def test_login_failure(self):
        """Title not starting with 'Welcome' indicates failure."""
        html = load_fixture("login_failure.html")
        assert parse_login_response(html) is False

    def test_no_title(self):
        """Missing title element returns False."""
        html = "<html><body>No title</body></html>"
        assert parse_login_response(html) is False

    def test_empty_title(self):
        """Empty title returns False."""
        html = "<html><head><title></title></head></html>"
        assert parse_login_response(html) is False

    def test_welcome_prefix_case_sensitive(self):
        """Welcome check is case-sensitive."""
        html = "<html><head><title>welcome lowercase</title></head></html>"
        assert parse_login_response(html) is False

        html = "<html><head><title>Welcome Uppercase</title></head></html>"
        assert parse_login_response(html) is True


class TestParseAvailability:
    """Tests for parse_availability function."""

    def test_with_available_slots(self):
        """Parse availability with bookable slots."""
        html = load_fixture("availability_with_slots.html")
        slots = parse_availability(html)

        assert len(slots) == 3

        # Check first slot
        assert slots[0].time == "09:00"
        assert slots[0].can_book is True
        assert slots[0].booking_form == {
            "date": "2024-01-15",
            "time": "0900",
            "course": "1",
            "holes": "18",
        }

        # Check second slot
        assert slots[1].time == "09:30"
        assert slots[1].booking_form["time"] == "0930"

        # Check third slot
        assert slots[2].time == "10:00"
        assert slots[2].booking_form["time"] == "1000"

    def test_blocked_slots_filtered(self):
        """Slots with players booked or competitions are filtered out."""
        html = load_fixture("availability_blocked.html")
        slots = parse_availability(html)

        # All slots should be filtered:
        # - 09:00 has players booked
        # - 09:30 has competition block
        # - 10:00 has player booked (and no booking button)
        assert len(slots) == 0

    def test_empty_availability(self):
        """Handle empty availability page."""
        html = load_fixture("availability_empty.html")
        slots = parse_availability(html)

        assert len(slots) == 0

    def test_no_booking_button_filtered(self):
        """Rows without a.inlineBooking are filtered out."""
        html = """
        <html><body>
        <tr class="canreserve">
            <th>09:00</th>
            <td class="slot-actions">
                <form><input name="date" value="2024-01-15"/></form>
                <!-- No a.inlineBooking -->
            </td>
        </tr>
        </body></html>
        """
        slots = parse_availability(html)
        assert len(slots) == 0

    def test_players_booked_filtered(self):
        """Rows with span.player-name are filtered out."""
        html = """
        <html><body>
        <tr class="canreserve">
            <th>09:00</th>
            <td class="slot-actions">
                <form><input name="date" value="2024-01-15"/></form>
                <a class="inlineBooking" href="#">Book</a>
                <span class="player-name">John Doe</span>
            </td>
        </tr>
        </body></html>
        """
        slots = parse_availability(html)
        assert len(slots) == 0

    def test_competition_blocked_filtered(self):
        """Rows with div.comp-item are filtered out."""
        html = """
        <html><body>
        <tr class="canreserve">
            <th>09:00</th>
            <td class="slot-actions">
                <form><input name="date" value="2024-01-15"/></form>
                <a class="inlineBooking" href="#">Book</a>
                <div class="comp-item">Competition</div>
            </td>
        </tr>
        </body></html>
        """
        slots = parse_availability(html)
        assert len(slots) == 0

    def test_malformed_html_handled(self):
        """Gracefully handle malformed HTML."""
        html = "<html><body><tr class='canreserve'><th>09:00"  # Unclosed tags
        slots = parse_availability(html)
        # Should not raise, may return empty or partial results
        assert isinstance(slots, list)


class TestParseBookingResponse:
    """Tests for parse_booking_response function."""

    def test_booking_success(self):
        """Successful booking returns True."""
        html = load_fixture("booking_success.html")
        success, error = parse_booking_response(html)

        assert success is True
        assert error == ""

    def test_booking_failure(self):
        """Failed booking returns False with error message."""
        html = load_fixture("booking_failure.html")
        success, error = parse_booking_response(html)

        assert success is False
        assert "time slot may no longer be available" in error.lower()

    def test_wrong_confirmation_message(self):
        """Unexpected confirmation message returns failure."""
        html = """
        <html><body>
        <div id="globalwrap">
            <div class="user-messages alert user-message-success alert-success">
                <ul><li><strong>Unexpected message</strong></li></ul>
            </div>
        </div>
        </body></html>
        """
        success, error = parse_booking_response(html)

        assert success is False

    def test_no_success_element(self):
        """Missing success element returns failure."""
        html = "<html><body>No confirmation</body></html>"
        success, error = parse_booking_response(html)

        assert success is False


class TestExtractBookingId:
    """Tests for extract_booking_id function."""

    def test_extract_from_url_with_question_mark(self):
        """Extract booking ID from URL with ?edit=."""
        url = "https://example.com/memberbooking/?edit=ABC123&other=param"
        assert extract_booking_id(url) == "ABC123"

    def test_extract_from_url_with_ampersand(self):
        """Extract booking ID from URL with &edit=."""
        url = "https://example.com/memberbooking/?foo=bar&edit=XYZ789"
        assert extract_booking_id(url) == "XYZ789"

    def test_no_booking_id(self):
        """Return None when no booking ID in URL."""
        url = "https://example.com/memberbooking/?other=param"
        assert extract_booking_id(url) is None

    def test_empty_url(self):
        """Return None for empty URL."""
        assert extract_booking_id("") is None

    def test_booking_id_only_param(self):
        """Handle URL where edit is the only parameter."""
        url = "https://example.com/memberbooking/?edit=ONLY123"
        assert extract_booking_id(url) == "ONLY123"

    def test_booking_id_with_special_chars(self):
        """Handle booking ID with alphanumeric characters."""
        url = "https://example.com/?edit=Book2024Jan15"
        assert extract_booking_id(url) == "Book2024Jan15"
