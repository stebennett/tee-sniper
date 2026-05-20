"""FastMCP server entrypoint."""

from __future__ import annotations

import asyncio
import contextlib
import sys
from collections.abc import AsyncIterator

import httpx
from fastmcp import FastMCP

from tee_sniper_mcp.api_client import ApiClient
from tee_sniper_mcp.auth import AuthManager
from tee_sniper_mcp.config import Config, ConfigError, load_config
from tee_sniper_mcp.tools import Tools


@contextlib.asynccontextmanager
async def build_server(*, config: Config) -> AsyncIterator[FastMCP]:
    """Build a configured FastMCP server with all tools registered.

    Yields the server inside an async context that owns the underlying
    httpx.AsyncClient lifetime.
    """
    mcp = FastMCP(name="tee-sniper", instructions=_INSTRUCTIONS)

    async with httpx.AsyncClient(timeout=30.0) as http:
        auth = AuthManager(config, http)
        api = ApiClient(config, auth, http)
        tools = Tools(config=config, api=api)

        mcp.tool(name="find_tee_times", description=_FIND_DESCRIPTION)(tools.find_tee_times)
        mcp.tool(name="book_tee_time", description=_BOOK_DESCRIPTION)(tools.book_tee_time)
        mcp.tool(name="list_partners", description=_LIST_PARTNERS_DESCRIPTION)(tools.list_partners)
        mcp.tool(name="add_partners", description=_ADD_PARTNERS_DESCRIPTION)(tools.add_partners)

        mcp.tool(name="create_one_shot_wanted", description=_CREATE_ONE_SHOT_DESCRIPTION)(
            tools.create_one_shot_wanted
        )
        mcp.tool(name="create_recurring_wanted", description=_CREATE_RECURRING_DESCRIPTION)(
            tools.create_recurring_wanted
        )
        mcp.tool(name="list_wanted", description=_LIST_WANTED_DESCRIPTION)(tools.list_wanted)
        mcp.tool(name="get_wanted", description=_GET_WANTED_DESCRIPTION)(tools.get_wanted)
        mcp.tool(name="update_wanted", description=_UPDATE_WANTED_DESCRIPTION)(tools.update_wanted)
        mcp.tool(name="set_wanted_enabled", description=_SET_WANTED_ENABLED_DESCRIPTION)(
            tools.set_wanted_enabled
        )
        mcp.tool(name="delete_wanted", description=_DELETE_WANTED_DESCRIPTION)(tools.delete_wanted)

        yield mcp


_INSTRUCTIONS = """tee-sniper exposes golf tee-time booking operations.

Login is handled transparently the first time you call any tool — you do not
need to authenticate explicitly."""

_FIND_DESCRIPTION = """Find available tee times for a given date.

date: 'today', 'tomorrow', 'next saturday', 'this friday', 'in 3 days', or ISO 'YYYY-MM-DD'.
Use either explicit start_time/end_time (e.g. '15:00', '3pm') or a time_of_day band:
early_morning (06–09), morning (09–12), midday (11–14), afternoon (12–17),
early_evening (17–19), all_day (no filter). Explicit times override the band."""

_BOOK_DESCRIPTION = """Book a tee time. num_slots is 1–4 (default 1). Set dry_run=true to simulate."""

_LIST_PARTNERS_DESCRIPTION = """List configured playing partners (id and name) you can add to a booking."""

_ADD_PARTNERS_DESCRIPTION = """Add 1–3 playing partners (by id from list_partners) to an existing booking."""

_CREATE_ONE_SHOT_DESCRIPTION = """Create a one-shot wanted tee-time request: the worker auto-books a slot for a single target_date when it becomes available.

target_date: 'next saturday', 'in 8 days', 'tomorrow', or ISO 'YYYY-MM-DD'.
start_time/end_time: e.g. '15:00' or '3pm' (acceptable booking window).
num_slots: 1-4 (default 1). partners: optional list of partner ids.
Credentials are taken from server config automatically."""

_CREATE_RECURRING_DESCRIPTION = """Create a recurring wanted tee-time request: the worker auto-books that weekday each time it enters the booking window.

day_of_week: weekday name ('saturday'/'sat') or int 0-6 where 0=Monday … 6=Sunday.
start_time/end_time: e.g. '15:00' or '3pm'. end_date: optional last date ('YYYY-MM-DD' or natural language); omit for open-ended.
num_slots: 1-4 (default 1). partners: optional list of partner ids.
Credentials are taken from server config automatically."""

_LIST_WANTED_DESCRIPTION = """List wanted tee-time requests (trimmed summaries). Optional status filter: pending, booked, expired, disabled."""

_GET_WANTED_DESCRIPTION = """Get one wanted request by id, including its full attempt history."""

_UPDATE_WANTED_DESCRIPTION = """Edit a wanted request. Provide only the fields to change: start_time, end_time, num_slots, partners. Cannot change kind/date/day_of_week (recreate instead) or pause it (use set_wanted_enabled)."""

_SET_WANTED_ENABLED_DESCRIPTION = """Pause or resume a wanted request. enabled=false disables it; enabled=true restores a disabled request to pending."""

_DELETE_WANTED_DESCRIPTION = """Permanently delete a wanted request by id."""


async def _async_main() -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"tee-sniper-mcp: configuration error: {exc}", file=sys.stderr)
        return 2

    async with build_server(config=config) as mcp:
        await mcp.run_stdio_async()
    return 0


def main() -> None:
    sys.exit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()
