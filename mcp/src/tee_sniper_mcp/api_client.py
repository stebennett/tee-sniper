"""Thin async HTTP client for the tee-sniper REST API."""

from __future__ import annotations

from typing import Any

import httpx

from tee_sniper_mcp.auth import AuthError, AuthManager
from tee_sniper_mcp.config import Config


class ApiError(Exception):
    """Raised when the REST API returns a non-success status."""


class ApiClient:
    """Authenticated wrapper that attaches Bearer tokens and retries once on 401."""

    def __init__(
        self,
        config: Config,
        auth: AuthManager,
        http_client: httpx.AsyncClient,
    ) -> None:
        self._config = config
        self._auth = auth
        self._client = http_client

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request("POST", path, params=params, json=json)

    async def patch(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request("PATCH", path, params=params, json=json)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._config.api_base_url}{path}"
        for attempt in (1, 2):
            try:
                token = await self._auth.get_token()
            except AuthError as exc:
                raise ApiError(str(exc)) from exc
            try:
                response = await self._client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers={"Authorization": f"Bearer {token}"},
                )
            except httpx.HTTPError as exc:
                raise ApiError(f"{method} {path} failed: {exc}") from exc

            if response.status_code == 401 and attempt == 1:
                self._auth.invalidate()
                continue

            if response.status_code >= 400:
                detail = self._extract_detail(response)
                raise ApiError(f"{method} {path} -> {response.status_code}: {detail}")

            if not response.content:
                return None
            return response.json()

        # Unreachable — loop returns or raises on every path.
        raise ApiError("unreachable")

    @staticmethod
    def _extract_detail(response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text or response.reason_phrase
        if isinstance(body, dict):
            return body.get("detail", response.text)
        return response.text or response.reason_phrase
