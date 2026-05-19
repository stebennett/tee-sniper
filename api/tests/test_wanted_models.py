"""Tests for wanted-slot pydantic models."""

import datetime

import pytest
from pydantic import ValidationError

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


def _one_shot(**over) -> WantedSlot:
    base = dict(
        id="11111111-1111-1111-1111-111111111111",
        kind=WantedKind.ONE_SHOT,
        target_date=datetime.date(2026, 6, 1),
        start_time="08:00",
        end_time="10:00",
        num_slots=2,
        partners=["p1"],
        credentials="encrypted-blob",
        notify=Notify(to="+15550001111", from_="+15550002222"),
        status=WantedStatus.PENDING,
        attempts=[],
        created_at=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
    )
    base.update(over)
    return WantedSlot(**base)


def test_wanted_slot_json_roundtrip_preserves_fields():
    slot = _one_shot()
    restored = WantedSlot.model_validate_json(slot.model_dump_json())
    assert restored == slot
    assert restored.notify.from_ == "+15550002222"


def test_recurring_slot_requires_day_of_week():
    slot = WantedSlot(
        id="22222222-2222-2222-2222-222222222222",
        kind=WantedKind.RECURRING,
        day_of_week=5,  # Saturday (Monday=0)
        start_time="07:00",
        end_time="09:00",
        num_slots=1,
        partners=[],
        credentials="blob",
        notify=None,
        status=WantedStatus.PENDING,
        attempts=[],
        created_at=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
    )
    assert slot.day_of_week == 5
    assert slot.target_date is None


def test_create_one_shot_request_rejects_end_before_start():
    with pytest.raises(ValidationError):
        CreateOneShotRequest(
            target_date=datetime.date(2026, 6, 1),
            start_time="10:00",
            end_time="08:00",
            num_slots=1,
            partners=[],
            credentials="blob",
        )


def test_create_recurring_request_validates_day_of_week_range():
    with pytest.raises(ValidationError):
        CreateRecurringRequest(
            day_of_week=7,
            start_time="08:00",
            end_time="10:00",
            num_slots=1,
            partners=[],
            credentials="blob",
        )


def test_wanted_response_redacts_credentials():
    slot = _one_shot()
    resp = WantedResponse.from_slot(slot)
    dumped = resp.model_dump()
    assert "credentials" not in dumped
    assert dumped["has_credentials"] is True
    assert dumped["notify"]["to"] == "+15550001111"


def test_patch_request_all_fields_optional():
    patch = PatchWantedRequest()
    assert patch.model_dump(exclude_unset=True) == {}


def test_attempt_and_outcome_enum_serialize():
    att = Attempt(
        ts=datetime.datetime(2026, 5, 24, tzinfo=datetime.timezone.utc),
        target_date=datetime.date(2026, 6, 1),
        outcome=Outcome.BOOKED,
        booking_id="bk-1",
    )
    assert att.model_dump()["outcome"] == "booked"


def test_one_shot_slot_requires_target_date():
    with pytest.raises(ValidationError):
        WantedSlot(
            id="33333333-3333-3333-3333-333333333333",
            kind=WantedKind.ONE_SHOT,
            start_time="08:00",
            end_time="10:00",
            num_slots=1,
            partners=[],
            credentials="blob",
            notify=None,
            status=WantedStatus.PENDING,
            attempts=[],
            created_at=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
            updated_at=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
        )


def test_recurring_slot_missing_day_of_week_rejected():
    with pytest.raises(ValidationError):
        WantedSlot(
            id="44444444-4444-4444-4444-444444444444",
            kind=WantedKind.RECURRING,
            start_time="08:00",
            end_time="10:00",
            num_slots=1,
            partners=[],
            credentials="blob",
            notify=None,
            status=WantedStatus.PENDING,
            attempts=[],
            created_at=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
            updated_at=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
        )


def test_patch_request_rejects_end_before_start_when_both_provided():
    with pytest.raises(ValidationError):
        PatchWantedRequest(start_time="10:00", end_time="08:00")


@pytest.mark.parametrize("field", ["day_of_week", "kind", "target_date", "bogus"])
def test_patch_request_rejects_immutable_or_unknown_fields(field):
    with pytest.raises(ValidationError):
        PatchWantedRequest(**{field: 2})
