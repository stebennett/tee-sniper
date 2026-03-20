"""Booking API route handlers."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.config import Settings
from app.dependencies import (
    get_booking_client,
    get_encryption_service,
    get_session_manager,
    get_settings_dependency,
)
from app.models.requests import AddPartnersRequest, BookRequest, LoginRequest
from app.models.responses import (
    AddPartnersResponse,
    AvailabilityResponse,
    BookResponse,
    LoginResponse,
    TimeSlotResponse,
)
from app.services.booking_client import (
    BookingClient,
    BookingClientError,
    BookingError,
    LoginError,
)
from app.services.encryption import EncryptionError, EncryptionService
from app.services.session_manager import SessionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Booking"])


def _convert_date_api_to_client(date_str: str) -> str:
    """Convert date from API format (YYYY-MM-DD) to client format (DD-MM-YYYY)."""
    parts = date_str.split("-")
    return f"{parts[2]}-{parts[1]}-{parts[0]}"


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    body: LoginRequest,
    encryption: EncryptionService = Depends(get_encryption_service),
    session_manager: SessionManager = Depends(get_session_manager),
    settings: Settings = Depends(get_settings_dependency),
) -> LoginResponse:
    """Authenticate with the booking site and create a session."""
    try:
        username, pin = encryption.decrypt_credentials(body.credentials)
    except EncryptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid credentials: {exc}",
        ) from exc

    base_url = body.base_url or settings.base_url

    client = BookingClient(base_url=base_url)
    try:
        async with client:
            await client.login(username, pin)
            cookies = client.get_cookies()
    except LoginError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except BookingClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream service error: {exc}",
        ) from exc

    token = await session_manager.store_session(cookies, base_url)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=session_manager.ttl)

    return LoginResponse(access_token=token, expires_at=expires_at)


@router.get(
    "/{date}/times",
    response_model=AvailabilityResponse,
    status_code=status.HTTP_200_OK,
)
async def get_times(
    date: str,
    start: str | None = Query(default=None, description="Start time filter (HH:MM)"),
    end: str | None = Query(default=None, description="End time filter (HH:MM)"),
    client: BookingClient = Depends(get_booking_client),
) -> AvailabilityResponse:
    """Get available tee times for a given date."""
    client_date = _convert_date_api_to_client(date)

    try:
        slots = await client.get_availability(client_date)
    except BookingClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream service error: {exc}",
        ) from exc

    total_count = len(slots)

    if start:
        slots = [s for s in slots if s.time >= start]
    if end:
        slots = [s for s in slots if s.time <= end]

    times = [
        TimeSlotResponse(
            time=s.time,
            can_book=s.can_book,
            booking_form=s.booking_form,
        )
        for s in slots
    ]

    return AvailabilityResponse(
        date=date,
        times=times,
        filtered_count=len(times),
        total_count=total_count,
    )


@router.post(
    "/{date}/time/{time}/book",
    response_model=BookResponse,
    status_code=status.HTTP_200_OK,
)
async def book_time(
    date: str,
    time: str,
    body: BookRequest,
    client: BookingClient = Depends(get_booking_client),
) -> BookResponse:
    """Book a specific tee time slot."""
    client_date = _convert_date_api_to_client(date)

    try:
        slots = await client.get_availability(client_date)
    except BookingClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream service error: {exc}",
        ) from exc

    # Find matching bookable slot
    matching = [s for s in slots if s.time == time and s.can_book]
    if not matching:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No bookable slot found for {time} on {date}",
        )

    slot = matching[0]

    try:
        booking_id = await client.book_time_slot(slot, body.num_slots, body.dry_run)
    except BookingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except BookingClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream service error: {exc}",
        ) from exc

    return BookResponse(
        booking_id=booking_id,
        date=date,
        time=time,
        slots_booked=body.num_slots,
    )


@router.patch(
    "/bookings/{booking_id}",
    response_model=AddPartnersResponse,
    status_code=status.HTTP_200_OK,
)
async def add_partners(
    booking_id: str,
    body: AddPartnersRequest,
    client: BookingClient = Depends(get_booking_client),
) -> AddPartnersResponse | JSONResponse:
    """Add playing partners to an existing booking."""
    added: list[str] = []
    failed: list[str] = []

    for i, partner_id in enumerate(body.partners):
        slot_num = i + 2  # Slots 2, 3, 4 (slot 1 is main player)
        try:
            await client.add_partner(booking_id, partner_id, slot_num, body.dry_run)
            added.append(partner_id)
        except (BookingClientError, BookingError) as exc:
            logger.warning(
                "Failed to add partner",
                extra={
                    "booking_id": booking_id,
                    "partner_id": partner_id,
                    "slot_num": slot_num,
                    "error": str(exc),
                },
            )
            failed.append(partner_id)

    if not added:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to add any partners",
        )

    response = AddPartnersResponse(
        booking_id=booking_id,
        partners_added=added,
        partners_failed=failed,
        message=(
            "All partners added successfully"
            if not failed
            else f"Partial success: {len(added)} added, {len(failed)} failed"
        ),
    )

    if failed:
        return JSONResponse(
            status_code=status.HTTP_207_MULTI_STATUS,
            content=response.model_dump(),
        )

    return response
