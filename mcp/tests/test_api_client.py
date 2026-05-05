"""Tests for ApiClient (auth + 401-retry wrapper)."""

import datetime as dt

import httpx
import pytest
import respx

from tee_sniper_mcp.api_client import ApiClient, ApiError
from tee_sniper_mcp.auth import AuthManager
from tee_sniper_mcp.config import Config


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


@respx.mock
async def test_get_attaches_bearer_token(config: Config) -> None:
    respx.post("http://api.test/api/login").mock(return_value=_login_response())
    times = respx.get("http://api.test/api/2026-05-10/times").mock(
        return_value=httpx.Response(200, json={"date": "2026-05-10", "times": [], "filtered_count": 0, "total_count": 0})
    )

    async with httpx.AsyncClient() as http:
        api = ApiClient(config, AuthManager(config, http), http)
        await api.get("/api/2026-05-10/times")

    assert times.calls.last.request.headers["authorization"] == "Bearer tok-1"


@respx.mock
async def test_401_triggers_one_retry(config: Config) -> None:
    login = respx.post("http://api.test/api/login").mock(
        side_effect=[_login_response(), _login_response()]
    )
    times = respx.get("http://api.test/api/2026-05-10/times").mock(
        side_effect=[httpx.Response(401, json={"detail": "expired"}), httpx.Response(200, json={"ok": True})]
    )

    async with httpx.AsyncClient() as http:
        api = ApiClient(config, AuthManager(config, http), http)
        result = await api.get("/api/2026-05-10/times")

    assert result == {"ok": True}
    assert login.call_count == 2
    assert times.call_count == 2


@respx.mock
async def test_persistent_401_raises(config: Config) -> None:
    respx.post("http://api.test/api/login").mock(side_effect=[_login_response(), _login_response()])
    respx.get("http://api.test/api/x").mock(
        return_value=httpx.Response(401, json={"detail": "still bad"})
    )

    async with httpx.AsyncClient() as http:
        api = ApiClient(config, AuthManager(config, http), http)
        with pytest.raises(ApiError, match="still bad"):
            await api.get("/api/x")


@respx.mock
async def test_non_401_error_surfaces(config: Config) -> None:
    respx.post("http://api.test/api/login").mock(return_value=_login_response())
    respx.get("http://api.test/api/x").mock(
        return_value=httpx.Response(502, json={"detail": "upstream"})
    )

    async with httpx.AsyncClient() as http:
        api = ApiClient(config, AuthManager(config, http), http)
        with pytest.raises(ApiError, match="upstream"):
            await api.get("/api/x")


@respx.mock
async def test_post_passes_json_body(config: Config) -> None:
    respx.post("http://api.test/api/login").mock(return_value=_login_response())
    book = respx.post("http://api.test/api/2026-05-10/time/08:00/book").mock(
        return_value=httpx.Response(200, json={"booking_id": "b1"})
    )

    async with httpx.AsyncClient() as http:
        api = ApiClient(config, AuthManager(config, http), http)
        result = await api.post(
            "/api/2026-05-10/time/08:00/book",
            json={"num_slots": 2, "dry_run": False},
        )

    assert result == {"booking_id": "b1"}
    import json as _json
    body = _json.loads(book.calls.last.request.read())
    assert body == {"num_slots": 2, "dry_run": False}
