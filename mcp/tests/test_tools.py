"""Tests for the four MCP tools."""

import datetime as dt

import httpx
import pytest
import respx

from tee_sniper_mcp.api_client import ApiClient
from tee_sniper_mcp.auth import AuthManager
from tee_sniper_mcp.config import Config
from tee_sniper_mcp.tools import Tools


@pytest.fixture
def config() -> Config:
    return Config(
        api_base_url="http://api.test",
        username="alice",
        pin="1234",
        shared_secret="s3cret",
        time_bands_override=None,
    )


def _login_response() -> httpx.Response:
    expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=30)).isoformat()
    return httpx.Response(200, json={"access_token": "tok-1", "expires_at": expires})


@pytest.fixture
async def tools(config: Config):
    async with httpx.AsyncClient() as http:
        respx.post("http://api.test/api/login").mock(return_value=_login_response())
        api = ApiClient(config, AuthManager(config, http), http)
        yield Tools(config=config, api=api, today=lambda: dt.date(2026, 5, 4))


@respx.mock
async def test_find_tee_times_with_band(tools: Tools) -> None:
    route = respx.get("http://api.test/api/2026-05-05/times").mock(
        return_value=httpx.Response(
            200,
            json={
                "date": "2026-05-05",
                "times": [
                    {"time": "07:00", "can_book": True, "booking_form": {"slot": "1"}},
                    {"time": "08:00", "can_book": False, "booking_form": {}},
                ],
                "filtered_count": 2,
                "total_count": 5,
            },
        )
    )

    result = await tools.find_tee_times(date="tomorrow", time_of_day="early_morning")

    assert result == {
        "date": "2026-05-05",
        "slots": [{"time": "07:00", "can_book": True}, {"time": "08:00", "can_book": False}],
    }
    qs = route.calls.last.request.url.params
    assert qs["start"] == "06:00"
    assert qs["end"] == "09:00"


@respx.mock
async def test_find_tee_times_explicit_times_override_band(tools: Tools) -> None:
    route = respx.get("http://api.test/api/2026-05-05/times").mock(
        return_value=httpx.Response(
            200,
            json={"date": "2026-05-05", "times": [], "filtered_count": 0, "total_count": 0},
        )
    )

    await tools.find_tee_times(
        date="tomorrow",
        start_time="3pm",
        end_time="5pm",
        time_of_day="early_morning",
    )

    qs = route.calls.last.request.url.params
    assert qs["start"] == "15:00"
    assert qs["end"] == "17:00"


async def test_find_tee_times_invalid_date_returns_error(tools: Tools) -> None:
    result = await tools.find_tee_times(date="blursday")
    assert "error" in result
    assert "blursday" in result["error"]


@respx.mock
async def test_book_tee_time_passes_through(tools: Tools) -> None:
    route = respx.post("http://api.test/api/2026-05-05/time/08:00/book").mock(
        return_value=httpx.Response(
            200,
            json={
                "booking_id": "b-1",
                "date": "2026-05-05",
                "time": "08:00",
                "slots_booked": 2,
                "message": "ok",
            },
        )
    )

    result = await tools.book_tee_time(date="tomorrow", time="8am", num_slots=2)

    assert result == {
        "booking_id": "b-1",
        "date": "2026-05-05",
        "time": "08:00",
        "num_slots": 2,
        "dry_run": False,
    }
    body = route.calls.last.request.read()
    assert b'"num_slots":2' in body
    assert b'"dry_run":false' in body


@respx.mock
async def test_list_partners_normalises_response(tools: Tools) -> None:
    respx.get("http://api.test/api/partners").mock(
        return_value=httpx.Response(
            200, json={"partners": [{"id": "id1", "name": "Alice"}, {"id": "id2", "name": "Bob"}]}
        )
    )

    result = await tools.list_partners()

    assert result == {"partners": [{"id": "id1", "name": "Alice"}, {"id": "id2", "name": "Bob"}]}


@respx.mock
async def test_add_partners_passes_through(tools: Tools) -> None:
    route = respx.patch("http://api.test/api/bookings/b-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "booking_id": "b-1",
                "partners_added": ["id1", "id2"],
                "partners_failed": [],
                "message": "ok",
            },
        )
    )

    result = await tools.add_partners(booking_id="b-1", partner_ids=["id1", "id2"])

    assert result == {
        "booking_id": "b-1",
        "partners_added": ["id1", "id2"],
        "partners_failed": [],
    }
    body = route.calls.last.request.read()
    assert b'"partners":["id1","id2"]' in body


@respx.mock
async def test_api_error_surfaces_as_error_dict(tools: Tools) -> None:
    respx.get("http://api.test/api/2026-05-05/times").mock(
        return_value=httpx.Response(502, json={"detail": "upstream broken"})
    )

    result = await tools.find_tee_times(date="tomorrow")

    assert "error" in result
    assert "upstream broken" in result["error"]
