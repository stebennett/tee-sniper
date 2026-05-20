"""Tests for date / time / band parsing."""

import datetime as dt

import pytest

from tee_sniper_mcp.dates import (
    DateParseError,
    DEFAULT_BANDS,
    parse_date,
    parse_day_of_week,
    parse_time,
    resolve_band,
    resolve_window,
)


@pytest.fixture
def today() -> dt.date:
    return dt.date(2026, 5, 4)  # a Monday


def test_parse_date_iso(today: dt.date) -> None:
    assert parse_date("2026-06-01", today=today) == dt.date(2026, 6, 1)


def test_parse_date_today(today: dt.date) -> None:
    assert parse_date("today", today=today) == today


def test_parse_date_tomorrow(today: dt.date) -> None:
    assert parse_date("Tomorrow", today=today) == dt.date(2026, 5, 5)


def test_parse_date_in_n_days(today: dt.date) -> None:
    assert parse_date("in 3 days", today=today) == dt.date(2026, 5, 7)


def test_parse_date_next_weekday(today: dt.date) -> None:
    # today=Mon 2026-05-04, "next saturday" => 2026-05-09
    assert parse_date("next saturday", today=today) == dt.date(2026, 5, 9)


def test_parse_date_this_weekday_future(today: dt.date) -> None:
    # today=Mon 2026-05-04, "this friday" => 2026-05-08
    assert parse_date("this friday", today=today) == dt.date(2026, 5, 8)


def test_parse_date_invalid_raises(today: dt.date) -> None:
    with pytest.raises(DateParseError):
        parse_date("blursday", today=today)


def test_parse_time_hhmm() -> None:
    assert parse_time("15:00") == "15:00"


def test_parse_time_3pm() -> None:
    assert parse_time("3pm") == "15:00"


def test_parse_time_3_30_pm() -> None:
    assert parse_time("3:30 PM") == "15:30"


def test_parse_time_invalid_raises() -> None:
    with pytest.raises(DateParseError):
        parse_time("teatime")


def test_resolve_band_default() -> None:
    assert resolve_band("early_morning") == ("06:00", "09:00")


def test_resolve_band_all_day_returns_none() -> None:
    assert resolve_band("all_day") == (None, None)


def test_resolve_band_unknown_raises() -> None:
    with pytest.raises(DateParseError):
        resolve_band("nightowl")


def test_resolve_band_with_override() -> None:
    override = {"morning": ["07:00", "11:00"]}
    assert resolve_band("morning", override=override) == ("07:00", "11:00")


def test_resolve_window_explicit_wins_over_band() -> None:
    start, end = resolve_window(start_time="08:30", end_time=None, time_of_day="afternoon")
    assert start == "08:30"
    assert end is None


def test_resolve_window_band_used_when_no_explicit() -> None:
    start, end = resolve_window(start_time=None, end_time=None, time_of_day="morning")
    assert (start, end) == DEFAULT_BANDS["morning"]


def test_resolve_window_no_filter() -> None:
    assert resolve_window(start_time=None, end_time=None, time_of_day=None) == (None, None)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("monday", 0),
        ("Monday", 0),
        (" MON ", 0),
        ("sat", 5),
        ("saturday", 5),
        ("sunday", 6),
        ("0", 0),
        ("6", 6),
        (0, 0),
        (6, 6),
    ],
)
def test_parse_day_of_week_ok(value, expected) -> None:
    assert parse_day_of_week(value) == expected


@pytest.mark.parametrize("value", ["funday", "", "7", "-1", 7, -1, "mondayy"])
def test_parse_day_of_week_rejects_junk(value) -> None:
    with pytest.raises(DateParseError):
        parse_day_of_week(value)
