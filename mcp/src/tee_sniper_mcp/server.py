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
