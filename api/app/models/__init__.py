"""Pydantic models for request/response validation."""

from app.models.domain import TimeSlot
from app.models.requests import AddPartnersRequest, BookRequest, LoginRequest
from app.models.responses import (
    AddPartnersResponse,
    AvailabilityResponse,
    BookResponse,
    HealthResponse,
    LoginResponse,
    TimeSlotResponse,
)
from app.models.wanted import (
    Attempt,
    CreateOneShotRequest,
    CreateRecurringRequest,
    Notify,
    Outcome,
    PatchWantedRequest,
    WantedKind,
    WantedResponse,
    WantedSlot,
    WantedStatus,
)

__all__ = [
    "TimeSlot",
    "LoginRequest",
    "BookRequest",
    "AddPartnersRequest",
    "LoginResponse",
    "TimeSlotResponse",
    "AvailabilityResponse",
    "BookResponse",
    "AddPartnersResponse",
    "HealthResponse",
    "Attempt",
    "CreateOneShotRequest",
    "CreateRecurringRequest",
    "Notify",
    "Outcome",
    "PatchWantedRequest",
    "WantedKind",
    "WantedResponse",
    "WantedSlot",
    "WantedStatus",
]
