"""Pydantic models for wanted tee-time requests."""

from __future__ import annotations

import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class WantedKind(str, Enum):
    ONE_SHOT = "one_shot"
    RECURRING = "recurring"


class WantedStatus(str, Enum):
    PENDING = "pending"
    BOOKED = "booked"
    EXPIRED = "expired"
    DISABLED = "disabled"


class Outcome(str, Enum):
    BOOKED = "booked"
    NO_SLOTS = "no_slots"
    AUTH_FAILED = "auth_failed"
    UPSTREAM_ERROR = "upstream_error"
    BOOKING_FAILED = "booking_failed"


class Notify(BaseModel):
    to: str = Field(..., description="Destination phone number, E.164")
    from_: str | None = Field(
        default=None,
        alias="from",
        description="Sender number; falls back to server default when unset",
    )

    model_config = {"populate_by_name": True}


class Attempt(BaseModel):
    ts: datetime.datetime
    target_date: datetime.date
    outcome: Outcome
    booking_id: str | None = None
    error: str | None = None


_HHMM = r"^\d{2}:\d{2}$"


class WantedSlot(BaseModel):
    """Storage model persisted in Redis."""

    id: str
    kind: WantedKind
    target_date: datetime.date | None = None
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    end_date: datetime.date | None = None
    start_time: str = Field(..., pattern=_HHMM)
    end_time: str = Field(..., pattern=_HHMM)
    num_slots: int = Field(..., ge=1, le=4)
    partners: list[str] = Field(default_factory=list, max_length=3)
    credentials: str
    notify: Notify | None = None
    status: WantedStatus = WantedStatus.PENDING
    attempts: list[Attempt] = Field(default_factory=list)
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @model_validator(mode="after")
    def _check_kind_fields(self) -> "WantedSlot":
        if self.kind is WantedKind.ONE_SHOT and self.target_date is None:
            raise ValueError("one_shot requires target_date")
        if self.kind is WantedKind.RECURRING and self.day_of_week is None:
            raise ValueError("recurring requires day_of_week")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class _CreateBase(BaseModel):
    start_time: str = Field(..., pattern=_HHMM)
    end_time: str = Field(..., pattern=_HHMM)
    num_slots: int = Field(default=1, ge=1, le=4)
    partners: list[str] = Field(default_factory=list, max_length=3)
    credentials: str
    notify: Notify | None = None

    @model_validator(mode="after")
    def _window(self) -> "_CreateBase":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class CreateOneShotRequest(_CreateBase):
    target_date: datetime.date


class CreateRecurringRequest(_CreateBase):
    day_of_week: int = Field(..., ge=0, le=6)
    end_date: datetime.date | None = None


class PatchWantedRequest(BaseModel):
    start_time: str | None = Field(default=None, pattern=_HHMM)
    end_time: str | None = Field(default=None, pattern=_HHMM)
    num_slots: int | None = Field(default=None, ge=1, le=4)
    partners: list[str] | None = Field(default=None, max_length=3)
    notify: Notify | None = None
    disabled: bool | None = None
    credentials: str | None = None

    @model_validator(mode="after")
    def _window(self) -> "PatchWantedRequest":
        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be after start_time")
        return self


class WantedResponse(BaseModel):
    id: str
    kind: WantedKind
    target_date: datetime.date | None
    day_of_week: int | None
    end_date: datetime.date | None
    start_time: str
    end_time: str
    num_slots: int
    partners: list[str]
    has_credentials: bool
    notify: Notify | None
    status: WantedStatus
    attempts: list[Attempt]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @classmethod
    def from_slot(cls, slot: WantedSlot) -> "WantedResponse":
        data = slot.model_dump()
        data.pop("credentials")
        data["has_credentials"] = bool(slot.credentials)
        return cls.model_validate(data)
