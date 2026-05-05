"""Tests for AuthManager."""

import datetime as dt

import httpx
import pytest
import respx

from tee_sniper_mcp.auth import AuthError, AuthManager, encrypt_credentials
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


def test_encrypt_credentials_roundtrip(config: Config) -> None:
    """Locally-encrypted credentials must decrypt with the API's EncryptionService."""
    from app.services.encryption import EncryptionService  # type: ignore[import-not-found]

    encrypted = encrypt_credentials(config.username, config.pin, config.shared_secret)
    svc = EncryptionService(config.shared_secret)
    user, pin = svc.decrypt_credentials(encrypted)
    assert (user, pin) == ("alice", "1234")


@respx.mock
async def test_get_token_calls_login_once_then_caches(config: Config) -> None:
    expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=30)).isoformat()
    route = respx.post("http://api.test/api/login").mock(
        return_value=httpx.Response(200, json={"access_token": "tok-1", "expires_at": expires})
    )

    async with httpx.AsyncClient() as client:
        auth = AuthManager(config, client)
        assert await auth.get_token() == "tok-1"
        assert await auth.get_token() == "tok-1"

    assert route.call_count == 1


@respx.mock
async def test_invalidate_forces_relogin(config: Config) -> None:
    expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=30)).isoformat()
    route = respx.post("http://api.test/api/login").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "tok-1", "expires_at": expires}),
            httpx.Response(200, json={"access_token": "tok-2", "expires_at": expires}),
        ]
    )

    async with httpx.AsyncClient() as client:
        auth = AuthManager(config, client)
        assert await auth.get_token() == "tok-1"
        auth.invalidate()
        assert await auth.get_token() == "tok-2"

    assert route.call_count == 2


@respx.mock
async def test_login_failure_raises(config: Config) -> None:
    respx.post("http://api.test/api/login").mock(
        return_value=httpx.Response(401, json={"detail": "bad creds"})
    )

    async with httpx.AsyncClient() as client:
        auth = AuthManager(config, client)
        with pytest.raises(AuthError, match="bad creds"):
            await auth.get_token()


@respx.mock
async def test_unexpected_login_body_raises_auth_error(config: Config) -> None:
    respx.post("http://api.test/api/login").mock(
        return_value=httpx.Response(200, json={"foo": "bar"})
    )

    async with httpx.AsyncClient() as client:
        auth = AuthManager(config, client)
        with pytest.raises(AuthError, match="unexpected login response"):
            await auth.get_token()
