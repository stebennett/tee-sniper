"""Lazy login + token caching against the tee-sniper REST API."""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import hashlib
import os

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from tee_sniper_mcp.config import Config


class AuthError(Exception):
    """Raised when login fails or credentials are misconfigured."""


_NONCE_SIZE = 12  # 96 bits, matches api/app/services/encryption.py


def encrypt_credentials(username: str, pin: str, shared_secret: str) -> str:
    """Encrypt 'username:pin' with AES-256-GCM (matches api/ EncryptionService)."""
    key = hashlib.sha256(shared_secret.encode()).digest()
    aesgcm = AESGCM(key)
    nonce = os.urandom(_NONCE_SIZE)
    plaintext = f"{username}:{pin}".encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext).decode()


class AuthManager:
    """Caches a bearer token in memory; calls /api/login on miss or after invalidate()."""

    def __init__(self, config: Config, http_client: httpx.AsyncClient) -> None:
        self._config = config
        self._client = http_client
        self._token: str | None = None
        self._expires_at: dt.datetime | None = None
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        async with self._lock:
            if self._token and self._is_valid():
                return self._token
            await self._login()
            assert self._token is not None
            return self._token

    def invalidate(self) -> None:
        self._token = None
        self._expires_at = None

    def _is_valid(self) -> bool:
        if self._expires_at is None:
            return False
        # 30s grace to avoid races near expiry
        return dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=30) < self._expires_at

    async def _login(self) -> None:
        encrypted = encrypt_credentials(
            self._config.username,
            self._config.pin,
            self._config.shared_secret,
        )
        url = f"{self._config.api_base_url}/api/login"
        try:
            response = await self._client.post(url, json={"credentials": encrypted})
        except httpx.HTTPError as exc:
            raise AuthError(f"login request failed: {exc}") from exc

        if response.status_code != 200:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise AuthError(f"login failed ({response.status_code}): {detail}")

        body = response.json()
        try:
            self._token = body["access_token"]
            self._expires_at = dt.datetime.fromisoformat(body["expires_at"])
        except (KeyError, ValueError) as exc:
            raise AuthError(f"unexpected login response: {exc}") from exc
