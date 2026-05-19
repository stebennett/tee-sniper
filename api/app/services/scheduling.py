"""Pure scheduling predicate: is a wanted slot due on a given day?"""

import datetime

from app.models.wanted import Outcome, WantedKind, WantedSlot, WantedStatus

RELEASE_WINDOW_DAYS = 8


def target_for(slot: WantedSlot, today: datetime.date) -> datetime.date | None:
    """The play date this slot would attempt to book if run today."""
    if slot.kind is WantedKind.ONE_SHOT:
        return slot.target_date
    release = today + datetime.timedelta(days=RELEASE_WINDOW_DAYS)
    if release.weekday() != slot.day_of_week:
        return None
    return release


def is_due(slot: WantedSlot, today: datetime.date) -> bool:
    """True if the worker should attempt this slot today."""
    if slot.status in (
        WantedStatus.BOOKED,
        WantedStatus.EXPIRED,
        WantedStatus.DISABLED,
    ):
        return False

    release = today + datetime.timedelta(days=RELEASE_WINDOW_DAYS)

    if slot.kind is WantedKind.ONE_SHOT:
        td = slot.target_date
        return td is not None and today <= td <= release

    # Recurring
    target = target_for(slot, today)
    if target is None:
        return False
    if slot.end_date is not None and target > slot.end_date:
        return False
    already_booked = any(
        a.outcome is Outcome.BOOKED and a.target_date == target
        for a in slot.attempts
    )
    return not already_booked
