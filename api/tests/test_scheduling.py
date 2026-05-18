"""Tests for the is_due / target_for scheduling predicate."""

import datetime

from app.models.wanted import (
    Attempt,
    Notify,
    Outcome,
    WantedKind,
    WantedSlot,
    WantedStatus,
)
from app.services.scheduling import RELEASE_WINDOW_DAYS, is_due, target_for

TODAY = datetime.date(2026, 5, 16)  # a Saturday
RELEASE = TODAY + datetime.timedelta(days=RELEASE_WINDOW_DAYS)  # 2026-05-24, Sunday


def _slot(**over) -> WantedSlot:
    base = dict(
        id="x",
        kind=WantedKind.ONE_SHOT,
        target_date=RELEASE,
        start_time="08:00",
        end_time="10:00",
        num_slots=1,
        partners=[],
        credentials="blob",
        notify=None,
        status=WantedStatus.PENDING,
        attempts=[],
        created_at=datetime.datetime(2026, 5, 1, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(2026, 5, 1, tzinfo=datetime.timezone.utc),
    )
    base.update(over)
    return WantedSlot(**base)


def test_one_shot_in_release_window_is_due():
    assert is_due(_slot(target_date=RELEASE), TODAY) is True
    assert target_for(_slot(target_date=RELEASE), TODAY) == RELEASE


def test_one_shot_inside_8_day_window_is_due():
    near = TODAY + datetime.timedelta(days=3)
    assert is_due(_slot(target_date=near), TODAY) is True


def test_one_shot_beyond_release_window_not_due():
    far = RELEASE + datetime.timedelta(days=1)
    assert is_due(_slot(target_date=far), TODAY) is False


def test_one_shot_past_target_not_due():
    past = TODAY - datetime.timedelta(days=1)
    assert is_due(_slot(target_date=past), TODAY) is False


def test_terminal_or_disabled_never_due():
    assert is_due(_slot(status=WantedStatus.BOOKED), TODAY) is False
    assert is_due(_slot(status=WantedStatus.EXPIRED), TODAY) is False
    assert is_due(_slot(status=WantedStatus.DISABLED), TODAY) is False


def _recurring(**over) -> WantedSlot:
    defaults = dict(
        kind=WantedKind.RECURRING,
        target_date=None,
        day_of_week=RELEASE.weekday(),
    )
    defaults.update(over)
    return _slot(**defaults)


def test_recurring_due_when_release_matches_day_of_week():
    assert is_due(_recurring(), TODAY) is True
    assert target_for(_recurring(), TODAY) == RELEASE


def test_recurring_not_due_when_day_of_week_mismatch():
    assert is_due(_recurring(day_of_week=(RELEASE.weekday() + 1) % 7), TODAY) is False


def test_recurring_not_due_when_occurrence_already_booked():
    booked = Attempt(
        ts=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
        target_date=RELEASE,
        outcome=Outcome.BOOKED,
        booking_id="b1",
    )
    assert is_due(_recurring(attempts=[booked]), TODAY) is False


def test_recurring_due_again_for_a_different_occurrence():
    old = Attempt(
        ts=datetime.datetime(2026, 5, 9, tzinfo=datetime.timezone.utc),
        target_date=RELEASE - datetime.timedelta(days=7),
        outcome=Outcome.BOOKED,
        booking_id="b0",
    )
    assert is_due(_recurring(attempts=[old]), TODAY) is True


def test_recurring_past_end_date_not_due():
    assert is_due(_recurring(end_date=RELEASE - datetime.timedelta(days=1)), TODAY) is False
