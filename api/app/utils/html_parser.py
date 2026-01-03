"""HTML parsing utilities for booking client."""

import re

from bs4 import BeautifulSoup

from app.models.domain import TimeSlot


def parse_login_response(html: str) -> bool:
    """Check if login was successful by examining page title.

    Matches Go implementation: strings.HasPrefix(pageTitle, "Welcome")
    """
    soup = BeautifulSoup(html, "lxml")
    title = soup.find("title")
    if title is None:
        return False
    return title.text.strip().startswith("Welcome")


def parse_availability(html: str) -> list[TimeSlot]:
    """Parse availability HTML and return list of bookable TimeSlots.

    Matches Go implementation logic:
    - Selects tr.canreserve and tr.cantreserve rows
    - Checks for booking button (a.inlineBooking)
    - Checks for people booked (span.player-name)
    - Checks for blocked slots (div.comp-item)
    - Extracts form parameters from td.slot-actions form input
    - Only returns slots where: !peopleBooked && !blocked && bookingButton
    """
    soup = BeautifulSoup(html, "lxml")
    slots: list[TimeSlot] = []

    for row in soup.select("tr.canreserve, tr.cantreserve"):
        # Extract time from th element
        time_elem = row.find("th")
        if not time_elem:
            continue
        time_str = time_elem.text.strip()

        # Check booking conditions (matching Go logic)
        booking_button = row.select_one("a.inlineBooking") is not None
        people_booked = len(row.select("span.player-name")) > 0
        blocked = row.select_one("div.comp-item") is not None

        # Extract form parameters
        booking_form: dict[str, str] = {}
        for input_elem in row.select("td.slot-actions form input"):
            name = input_elem.get("name")
            value = input_elem.get("value", "")
            if name and value:  # Go checks nok && vok (both must exist)
                booking_form[name] = value

        # Filter: only include bookable slots (matching Go: !peopleBooked && !blocked && bookingButton)
        if not people_booked and not blocked and booking_button:
            slots.append(
                TimeSlot(
                    time=time_str,
                    can_book=booking_button,
                    booking_form=booking_form,
                )
            )

    return slots


def parse_booking_response(html: str) -> tuple[bool, str]:
    """Parse booking response.

    Returns (success, error_message).
    - success=True, error="" on success
    - success=False, error="message" on failure

    Matches Go implementation: checks for exact confirmation message.
    """
    soup = BeautifulSoup(html, "lxml")

    # Check for success message using exact selector from Go
    success_elem = soup.select_one(
        "#globalwrap > div.user-messages.alert.user-message-success.alert-success > ul > li > strong"
    )

    expected_message = "Now please enter the names of your playing partners."

    if success_elem and success_elem.text.strip() == expected_message:
        return True, ""

    return False, "Booking failed - time slot may no longer be available"


def extract_booking_id(url: str) -> str | None:
    """Extract booking ID from redirect URL.

    Matches Go implementation: regexp.MustCompile(`[?&]edit=([^&]+)`)
    """
    match = re.search(r"[?&]edit=([^&]+)", url)
    return match.group(1) if match else None
