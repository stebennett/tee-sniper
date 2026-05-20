"""Tests for the wanted-tee-time MCP tools."""

import datetime as dt
import json

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
            yield Tools(config=config, api=api, today=lambda: dt.date(2026, 5, 20))


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


@respx.mock
async def test_create_one_shot_wanted_ok(tools: Tools) -> None:
    route = respx.post("http://api.test/api/wanted", params={"kind": "one_shot"}).mock(
        return_value=httpx.Response(201, json=_slot())
    )

    result = await tools.create_one_shot_wanted(
        target_date="next wednesday",
        start_time="3pm",
        end_time="5pm",
        num_slots=2,
        partners=["p1"],
    )

    assert result == tools._summarize(_slot())
    body = json.loads(route.calls.last.request.read())
    assert body["target_date"] == "2026-05-27"  # today=2026-05-20 (Wed) -> next Wed = 2026-05-27
    assert body["start_time"] == "15:00"
    assert body["end_time"] == "17:00"
    assert body["num_slots"] == 2
    assert body["partners"] == ["p1"]
    # credentials auto-encrypted, never plaintext
    assert "credentials" in body
    assert body["credentials"] not in ("alice:1234", "")
    assert "1234" not in body["credentials"]


async def test_create_one_shot_wanted_bad_date(tools: Tools) -> None:
    result = await tools.create_one_shot_wanted(
        target_date="blursday", start_time="3pm", end_time="5pm"
    )
    assert "error" in result and "blursday" in result["error"]


@respx.mock
async def test_create_one_shot_wanted_surfaces_422(tools: Tools) -> None:
    respx.post("http://api.test/api/wanted", params={"kind": "one_shot"}).mock(
        return_value=httpx.Response(422, json={"detail": "end_time must be after start_time"})
    )
    result = await tools.create_one_shot_wanted(
        target_date="tomorrow", start_time="5pm", end_time="3pm"
    )
    assert "error" in result and "end_time must be after start_time" in result["error"]


def _recurring_slot(**over) -> dict:
    defaults = dict(
        kind="recurring",
        target_date=None,
        day_of_week=5,
        end_date="2026-08-01",
    )
    defaults.update(over)
    return _slot(**defaults)


@respx.mock
async def test_create_recurring_wanted_ok(tools: Tools) -> None:
    route = respx.post("http://api.test/api/wanted", params={"kind": "recurring"}).mock(
        return_value=httpx.Response(201, json=_recurring_slot())
    )

    result = await tools.create_recurring_wanted(
        day_of_week="saturday",
        start_time="3pm",
        end_time="5pm",
        end_date="2026-08-01",
    )

    assert result == tools._summarize(_recurring_slot())
    body = json.loads(route.calls.last.request.read())
    assert body["day_of_week"] == 5
    assert body["start_time"] == "15:00"
    assert body["end_time"] == "17:00"
    assert body["end_date"] == "2026-08-01"
    assert "credentials" in body
    assert body["credentials"] not in ("alice:1234", "")
    assert "1234" not in body["credentials"]


@respx.mock
async def test_create_recurring_wanted_surfaces_422(tools: Tools) -> None:
    respx.post("http://api.test/api/wanted", params={"kind": "recurring"}).mock(
        return_value=httpx.Response(422, json={"detail": "end_time must be after start_time"})
    )
    result = await tools.create_recurring_wanted(
        day_of_week="sat", start_time="5pm", end_time="3pm"
    )
    assert "error" in result and "end_time must be after start_time" in result["error"]


@respx.mock
async def test_create_recurring_wanted_no_end_date_omits_field(tools: Tools) -> None:
    route = respx.post("http://api.test/api/wanted", params={"kind": "recurring"}).mock(
        return_value=httpx.Response(201, json=_recurring_slot(end_date=None))
    )
    await tools.create_recurring_wanted(
        day_of_week="sat", start_time="3pm", end_time="5pm"
    )
    body = json.loads(route.calls.last.request.read())
    assert "end_date" not in body


async def test_create_recurring_wanted_bad_day(tools: Tools) -> None:
    result = await tools.create_recurring_wanted(
        day_of_week="funday", start_time="3pm", end_time="5pm"
    )
    assert "error" in result and "funday" in result["error"]


@respx.mock
async def test_list_wanted_no_filter(tools: Tools) -> None:
    route = respx.get("http://api.test/api/wanted").mock(
        return_value=httpx.Response(200, json=[_slot(), _recurring_slot()])
    )
    result = await tools.list_wanted()
    assert result == {
        "wanted": [tools._summarize(_slot()), tools._summarize(_recurring_slot())]
    }
    assert "status" not in route.calls.last.request.url.params


@respx.mock
async def test_list_wanted_with_status_filter(tools: Tools) -> None:
    route = respx.get("http://api.test/api/wanted", params={"status": "booked"}).mock(
        return_value=httpx.Response(200, json=[_slot(status="booked")])
    )
    result = await tools.list_wanted(status="booked")
    assert result["wanted"][0]["status"] == "booked"
    assert route.calls.last.request.url.params["status"] == "booked"


async def test_list_wanted_rejects_bad_status(tools: Tools) -> None:
    result = await tools.list_wanted(status="nope")
    assert "error" in result and "nope" in result["error"]
    assert "pending" in result["error"]


@respx.mock
async def test_get_wanted_returns_full_slot(tools: Tools) -> None:
    full = _slot(attempts=[
        {"ts": "2026-05-19T06:00:00+00:00", "target_date": "2026-05-27",
         "outcome": "no_slots", "booking_id": None, "error": None},
    ])
    respx.get("http://api.test/api/wanted/w-1").mock(
        return_value=httpx.Response(200, json=full)
    )
    result = await tools.get_wanted(wanted_id="w-1")
    assert result == full  # full passthrough, not summarized


@respx.mock
async def test_get_wanted_404(tools: Tools) -> None:
    respx.get("http://api.test/api/wanted/missing").mock(
        return_value=httpx.Response(404, json={"detail": "Wanted slot not found"})
    )
    result = await tools.get_wanted(wanted_id="missing")
    assert "error" in result and "not found" in result["error"]


@respx.mock
async def test_update_wanted_sends_only_provided_fields(tools: Tools) -> None:
    route = respx.patch("http://api.test/api/wanted/w-1").mock(
        return_value=httpx.Response(200, json=_slot(num_slots=3))
    )
    result = await tools.update_wanted(wanted_id="w-1", num_slots=3)
    assert result == tools._summarize(_slot(num_slots=3))
    body = json.loads(route.calls.last.request.read())
    assert body == {"num_slots": 3}


@respx.mock
async def test_update_wanted_parses_times(tools: Tools) -> None:
    route = respx.patch("http://api.test/api/wanted/w-1").mock(
        return_value=httpx.Response(200, json=_slot())
    )
    await tools.update_wanted(wanted_id="w-1", start_time="3pm", end_time="5pm")
    body = json.loads(route.calls.last.request.read())
    assert body == {"start_time": "15:00", "end_time": "17:00"}


async def test_update_wanted_no_fields_is_error(tools: Tools) -> None:
    result = await tools.update_wanted(wanted_id="w-1")
    assert "error" in result and "no fields" in result["error"].lower()


async def test_update_wanted_bad_time(tools: Tools) -> None:
    result = await tools.update_wanted(wanted_id="w-1", start_time="half past noon")
    assert "error" in result


@respx.mock
async def test_update_wanted_404(tools: Tools) -> None:
    respx.patch("http://api.test/api/wanted/missing").mock(
        return_value=httpx.Response(404, json={"detail": "Wanted slot not found"})
    )
    result = await tools.update_wanted(wanted_id="missing", num_slots=2)
    assert "error" in result and "not found" in result["error"]


@respx.mock
async def test_set_wanted_enabled_false_sends_disabled_true(tools: Tools) -> None:
    route = respx.patch("http://api.test/api/wanted/w-1").mock(
        return_value=httpx.Response(200, json=_slot(status="disabled"))
    )
    result = await tools.set_wanted_enabled(wanted_id="w-1", enabled=False)
    assert result == tools._summarize(_slot(status="disabled"))
    assert json.loads(route.calls.last.request.read()) == {"disabled": True}


@respx.mock
async def test_set_wanted_enabled_true_sends_disabled_false(tools: Tools) -> None:
    route = respx.patch("http://api.test/api/wanted/w-1").mock(
        return_value=httpx.Response(200, json=_slot(status="pending"))
    )
    await tools.set_wanted_enabled(wanted_id="w-1", enabled=True)
    assert json.loads(route.calls.last.request.read()) == {"disabled": False}


@respx.mock
async def test_delete_wanted_ok(tools: Tools) -> None:
    respx.delete("http://api.test/api/wanted/w-1").mock(
        return_value=httpx.Response(204)
    )
    result = await tools.delete_wanted(wanted_id="w-1")
    assert result == {"deleted": True, "id": "w-1"}


@respx.mock
async def test_delete_wanted_404(tools: Tools) -> None:
    respx.delete("http://api.test/api/wanted/missing").mock(
        return_value=httpx.Response(404, json={"detail": "Wanted slot not found"})
    )
    result = await tools.delete_wanted(wanted_id="missing")
    assert "error" in result and "not found" in result["error"]
