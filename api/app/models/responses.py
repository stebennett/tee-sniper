"""Pydantic models for API response serialization."""

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response for health check endpoint."""

    status: str = Field(default="healthy", description="Service health status")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Current server timestamp",
    )
    redis_connected: bool = Field(
        default=True,
        description="Whether Redis is connected and healthy",
    )


class LoginResponse(BaseModel):
    """Response for successful login."""

    access_token: str = Field(..., description="UUID token for authenticated requests")
    expires_at: datetime = Field(..., description="Token expiration timestamp")


class TimeSlotResponse(BaseModel):
    """Response representation of a time slot."""

    time: str = Field(..., description="Time in HH:MM format")
    can_book: bool = Field(..., description="Whether the slot is available")
    booking_form: dict[str, str] = Field(
        default_factory=dict,
        description="Form parameters for booking",
    )


class AvailabilityResponse(BaseModel):
    """Response for availability endpoint."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    times: list[TimeSlotResponse] = Field(..., description="List of available time slots")
    filtered_count: int = Field(..., description="Number of slots after filtering")
    total_count: int = Field(..., description="Total number of slots before filtering")


class BookResponse(BaseModel):
    """Response for successful booking."""

    booking_id: str = Field(..., description="Unique booking identifier")
    date: str = Field(..., description="Booking date in YYYY-MM-DD format")
    time: str = Field(..., description="Booking time in HH:MM format")
    slots_booked: int = Field(..., description="Number of slots booked")
    message: str = Field(default="Successfully booked tee time", description="Status message")


class AddPartnersResponse(BaseModel):
    """Response for partner addition."""

    booking_id: str = Field(..., description="Booking identifier")
    partners_added: list[str] = Field(..., description="Successfully added partner IDs")
    partners_failed: list[str] = Field(
        default_factory=list,
        description="Partner IDs that failed to be added",
    )
    message: str = Field(..., description="Status message")


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str = Field(..., description="Error description")
