"""Domain models representing business entities."""

from pydantic import BaseModel, Field


class TimeSlot(BaseModel):
    """Represents an available tee time slot."""

    time: str = Field(..., description="Time in HH:MM format", examples=["09:00", "14:30"])
    can_book: bool = Field(..., description="Whether the slot is available for booking")
    booking_form: dict[str, str] = Field(
        default_factory=dict,
        description="Form parameters extracted from HTML for booking",
    )
