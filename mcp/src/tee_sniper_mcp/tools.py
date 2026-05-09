"""MCP tool implementations.

Each method returns a JSON-friendly dict. On failure they return
{"error": "...", ...} rather than raising, so the LLM can act on the message.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any

from tee_sniper_mcp.api_client import ApiClient, ApiError
from tee_sniper_mcp.config import Config
from tee_sniper_mcp.dates import DateParseError, parse_date, parse_time, resolve_window


class Tools:
    """Bundle of the four MCP tool implementations."""

    def __init__(
        self,
        config: Config,
        api: ApiClient,
        today: Callable[[], dt.date] = dt.date.today,
    ) -> None:
        self._config = config
        self._api = api
        self._today = today

    async def find_tee_times(
        self,
        date: str,
        start_time: str | None = None,
        end_time: str | None = None,
        time_of_day: str | None = None,
    ) -> dict[str, Any]:
        """Find available tee times on a given date."""
        try:
            target = parse_date(date, today=self._today())
            start, end = resolve_window(
                start_time=start_time,
                end_time=end_time,
                time_of_day=time_of_day,
                bands_override=self._config.time_bands_override,
            )
        except DateParseError as exc:
            return {"error": str(exc)}

        params: dict[str, str] = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        try:
            response = await self._api.get(
                f"/api/{target.isoformat()}/times",
                params=params or None,
            )
        except ApiError as exc:
            return {"error": str(exc)}

        try:
            slots = [
                {"time": slot["time"], "can_book": slot["can_book"]}
                for slot in response.get("times", [])
            ]
            return {"date": response["date"], "slots": slots}
        except (KeyError, TypeError) as exc:
            return {"error": f"unexpected API response: {exc}"}

    async def book_tee_time(
        self,
        date: str,
        time: str,
        num_slots: int = 1,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Book a tee time."""
        try:
            target = parse_date(date, today=self._today())
            target_time = parse_time(time)
        except DateParseError as exc:
            return {"error": str(exc)}

        if not 1 <= num_slots <= 4:
            return {"error": "num_slots must be between 1 and 4"}

        try:
            response = await self._api.post(
                f"/api/{target.isoformat()}/time/{target_time}/book",
                json={"num_slots": num_slots, "dry_run": dry_run},
            )
        except ApiError as exc:
            return {"error": str(exc)}

        try:
            return {
                "booking_id": response["booking_id"],
                "date": response["date"],
                "time": response["time"],
                "num_slots": response["slots_booked"],
                "dry_run": dry_run,
            }
        except (KeyError, TypeError) as exc:
            return {"error": f"unexpected API response: {exc}"}

    async def list_partners(self) -> dict[str, Any]:
        """List configured playing partners."""
        try:
            response = await self._api.get("/api/partners")
        except ApiError as exc:
            return {"error": str(exc)}
        return {"partners": response.get("partners", [])}

    async def add_partners(
        self,
        booking_id: str,
        partner_ids: list[str],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Add 1–3 playing partners to an existing booking."""
        if not 1 <= len(partner_ids) <= 3:
            return {"error": "partner_ids must contain between 1 and 3 ids"}

        try:
            response = await self._api.patch(
                f"/api/bookings/{booking_id}",
                json={"partners": partner_ids, "dry_run": dry_run},
            )
        except ApiError as exc:
            return {"error": str(exc)}

        try:
            return {
                "booking_id": response["booking_id"],
                "partners_added": response.get("partners_added", []),
                "partners_failed": response.get("partners_failed", []),
            }
        except (KeyError, TypeError) as exc:
            return {"error": f"unexpected API response: {exc}"}
