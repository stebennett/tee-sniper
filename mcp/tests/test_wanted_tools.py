"""Tests for the wanted-tee-time MCP tools."""

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
    with respx.MockRouter(assert_all_called=False) as router:
        router.post("http://api.test/api/login").mock(return_value=_login_response())
        async with httpx.AsyncClient() as http:
            api = ApiClient(config, AuthManager(config, http), http)
            yield Tools(config=config, api=api, today=lambda: dt.date(2026, 5, 19))


def _slot(**over) -> dict:
    base = {
        "id": "w-1",
        "kind": "one_shot",
        "target_date": "2026-05-27",
        "day_of_week": None,
        "end_date": None,
        "start_time": "15:00",
        "end_time": "17:00",
        "num_slots": 2,
        "partners": ["p1"],
        "has_credentials": True,
        "notify": None,
        "status": "pending",
        "attempts": [],
        "created_at": "2026-05-19T10:00:00+00:00",
        "updated_at": "2026-05-19T10:00:00+00:00",
    }
    base.update(over)
    return base


def test_summarize_trims_and_keeps_last_outcome() -> None:
    slot = _slot(
        attempts=[
            {"ts": "2026-05-19T06:00:00+00:00", "target_date": "2026-05-27",
             "outcome": "no_slots", "booking_id": None, "error": None},
            {"ts": "2026-05-20T06:00:00+00:00", "target_date": "2026-05-27",
             "outcome": "booked", "booking_id": "b-9", "error": None},
        ]
    )
    assert Tools._summarize(slot) == {
        "id": "w-1",
        "kind": "one_shot",
        "status": "pending",
        "target_date": "2026-05-27",
        "day_of_week": None,
        "end_date": None,
        "start_time": "15:00",
        "end_time": "17:00",
        "num_slots": 2,
        "partners": ["p1"],
        "last_outcome": "booked",
    }


def test_summarize_no_attempts() -> None:
    assert Tools._summarize(_slot())["last_outcome"] is None
