"""Date, time, and time-of-day band parsing."""

from __future__ import annotations

import datetime as dt
import re
from typing import Mapping

from dateutil import parser as du_parser


class DateParseError(ValueError):
    """Raised when a date, time, or band cannot be parsed."""


DEFAULT_BANDS: Mapping[str, tuple[str | None, str | None]] = {
    "early_morning": ("06:00", "09:00"),
    "morning": ("09:00", "12:00"),
    "midday": ("11:00", "14:00"),
    "afternoon": ("12:00", "17:00"),
    "early_evening": ("17:00", "19:00"),
    "all_day": (None, None),
}

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def parse_date(value: str, *, today: dt.date | None = None) -> dt.date:
    """Parse a relative or absolute date string into a date."""
    if today is None:
        today = dt.date.today()
    s = value.strip().lower()

    if not s:
        raise DateParseError("empty date")

    if s == "today":
        return today
    if s == "tomorrow":
        return today + dt.timedelta(days=1)
    if s == "yesterday":
        return today - dt.timedelta(days=1)

    m = re.fullmatch(r"in (\d+) days?", s)
    if m:
        return today + dt.timedelta(days=int(m.group(1)))

    m = re.fullmatch(r"(this|next) ([a-z]+)", s)
    if m:
        qualifier, weekday = m.group(1), m.group(2)
        if weekday not in _WEEKDAYS:
            raise DateParseError(f"unknown weekday in '{value}'")
        target = _WEEKDAYS[weekday]
        delta = (target - today.weekday()) % 7
        if qualifier == "next" and delta == 0:
            delta = 7
        if qualifier == "this" and delta == 0:
            return today
        return today + dt.timedelta(days=delta)

    try:
        parsed = du_parser.parse(value, default=dt.datetime.combine(today, dt.time()))
    except (ValueError, OverflowError) as exc:
        raise DateParseError(f"could not parse date '{value}'") from exc
    return parsed.date()


def parse_time(value: str) -> str:
    """Parse a time string into 'HH:MM' 24-hour format."""
    s = value.strip()
    if not s:
        raise DateParseError("empty time")
    try:
        parsed = du_parser.parse(s)
    except (ValueError, OverflowError) as exc:
        raise DateParseError(f"could not parse time '{value}'") from exc
    return parsed.strftime("%H:%M")


def resolve_band(
    name: str,
    *,
    override: Mapping[str, list[str]] | None = None,
) -> tuple[str | None, str | None]:
    """Resolve a named time-of-day band to a (start, end) tuple."""
    if override and name in override:
        pair = override[name]
        if len(pair) != 2:
            raise DateParseError(f"override for band '{name}' must be [start, end]")
        return (pair[0] or None, pair[1] or None)
    if name not in DEFAULT_BANDS:
        raise DateParseError(f"unknown time_of_day band '{name}'")
    return DEFAULT_BANDS[name]


def resolve_window(
    *,
    start_time: str | None,
    end_time: str | None,
    time_of_day: str | None,
    bands_override: Mapping[str, list[str]] | None = None,
) -> tuple[str | None, str | None]:
    """Resolve final (start, end) window for a find_tee_times call."""
    if start_time or end_time:
        return (
            parse_time(start_time) if start_time else None,
            parse_time(end_time) if end_time else None,
        )
    if time_of_day:
        return resolve_band(time_of_day, override=bands_override)
    return (None, None)
