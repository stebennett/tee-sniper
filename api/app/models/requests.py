"""Pydantic models for API request validation."""

from pydantic import BaseModel, Field, HttpUrl


class LoginRequest(BaseModel):
    """Request body for login endpoint."""

    credentials: str = Field(
        ...,
        description="AES-256-GCM encrypted 'username:pin' string, base64 encoded",
    )
    base_url: HttpUrl = Field(
        ...,
        description="Base URL of the golf course booking site",
        examples=["https://golfcourse.example.com/"],
    )


class BookRequest(BaseModel):
    """Request body for booking a tee time."""

    num_slots: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Number of slots to book (including yourself)",
    )
    dry_run: bool = Field(
        default=False,
        description="If true, simulate booking without making actual reservation",
    )


class AddPartnersRequest(BaseModel):
    """Request body for adding playing partners to a booking."""

    partners: list[str] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="List of partner IDs to add to the booking",
    )
    dry_run: bool = Field(
        default=False,
        description="If true, simulate partner addition without making changes",
    )
