# Wanted Tee-Time MCP Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 7 MCP tools that proxy the `/api/wanted` endpoints so an LLM/user can create, inspect, edit, pause, and delete persisted auto-booking ("wanted tee-time") requests from Claude Desktop / MetaMCP.

**Architecture:** Extend the existing `Tools` class in `mcp/src/tee_sniper_mcp/tools.py`, register the new tools in `server.py`, and reuse the existing `ApiClient` (lazy login + 401 retry) and `dates.py` parsers. Credentials are auto-encrypted from config (same AES-GCM scheme as login); the LLM never sees them. Same return convention as existing tools: dict on success, `{"error": ...}` on failure, never raise.

**Tech Stack:** Python 3.14, FastMCP, httpx, respx (test HTTP mocking), pytest, uv.

**Spec:** `docs/superpowers/specs/2026-05-19-wanted-tee-times-mcp-tools-design.md`

**Workflow:** Implement on a new git worktree taken from `main` (created via `superpowers:using-git-worktrees` at execution time). Ship as a single combined PR (project preference for multi-phase work). Subagents commit locally only; the controller handles push/PR.

**Conventions confirmed against source:**
- `day_of_week`: int `0–6`, **0 = Monday … 6 = Sunday**. Confirmed: `api/app/services/scheduling.py` compares `release.weekday() != slot.day_of_week`, and Python `date.weekday()` is 0=Mon..6=Sun. The `_WEEKDAYS` map already in `dates.py` (`monday:0 … sunday:6`) matches.
- Test pattern: existing MCP tests use `respx` to mock HTTP at `http://api.test`, with a `tools` fixture wiring a real `ApiClient`/`AuthManager` over a mocked `/api/login`. New tests follow the same pattern.
- `ApiClient` returns parsed JSON, or `None` when the response has no body (204). Errors raise `ApiError`; `auth` failures raise `AuthError` (wrapped to `ApiError`).
- All `/api/wanted` endpoints are session-authed; `ApiClient` attaches the bearer token transparently.

**Run tests:** `cd mcp && uv run pytest`

---

### Task 1: `parse_day_of_week` helper in dates.py

**Files:**
- Modify: `mcp/src/tee_sniper_mcp/dates.py`
- Test: `mcp/tests/test_dates.py`

- [ ] **Step 1: Write the failing tests**

Append to `mcp/tests/test_dates.py`:

```python
import pytest

from tee_sniper_mcp.dates import DateParseError, parse_day_of_week


@pytest.mark.parametrize(
    "value,expected",
    [
        ("monday", 0),
        ("Monday", 0),
        (" MON ", 0),
        ("sat", 5),
        ("saturday", 5),
        ("sunday", 6),
        ("0", 0),
        ("6", 6),
        (0, 0),
        (6, 6),
    ],
)
def test_parse_day_of_week_ok(value, expected):
    assert parse_day_of_week(value) == expected


@pytest.mark.parametrize("value", ["funday", "", "7", "-1", 7, -1, "mondayy"])
def test_parse_day_of_week_rejects_junk(value):
    with pytest.raises(DateParseError):
        parse_day_of_week(value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mcp && uv run pytest tests/test_dates.py -k parse_day_of_week -v`
Expected: FAIL — `ImportError: cannot import name 'parse_day_of_week'`

- [ ] **Step 3: Implement the helper**

Add to `mcp/src/tee_sniper_mcp/dates.py` (after `parse_time`). Reuse the existing `_WEEKDAYS` map; add abbreviation support:

```python
_WEEKDAY_ABBR = {name[:3]: idx for name, idx in _WEEKDAYS.items()}


def parse_day_of_week(value: str | int) -> int:
    """Normalize a weekday to int 0-6 (0=Monday … 6=Sunday)."""
    if isinstance(value, bool):  # bool is an int subclass; reject explicitly
        raise DateParseError(f"invalid day_of_week: {value!r}")
    if isinstance(value, int):
        if 0 <= value <= 6:
            return value
        raise DateParseError(f"day_of_week out of range (0-6): {value}")

    s = value.strip().lower()
    if not s:
        raise DateParseError("empty day_of_week")
    if s in _WEEKDAYS:
        return _WEEKDAYS[s]
    if s in _WEEKDAY_ABBR:
        return _WEEKDAY_ABBR[s]
    if s.lstrip("-").isdigit():
        n = int(s)
        if 0 <= n <= 6:
            return n
        raise DateParseError(f"day_of_week out of range (0-6): {s}")
    raise DateParseError(f"unknown day_of_week '{value}'")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd mcp && uv run pytest tests/test_dates.py -k parse_day_of_week -v`
Expected: PASS (all parametrized cases)

- [ ] **Step 5: Commit**

```bash
git add mcp/src/tee_sniper_mcp/dates.py mcp/tests/test_dates.py
git commit -m "feat(mcp): add parse_day_of_week helper"
```

---

### Task 2: Shared test fixtures + `_summarize` helper

**Files:**
- Modify: `mcp/src/tee_sniper_mcp/tools.py`
- Create: `mcp/tests/test_wanted_tools.py`

- [ ] **Step 1: Write the failing test**

Create `mcp/tests/test_wanted_tools.py`:

```python
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


def test_summarize_trims_and_keeps_last_outcome(tools: Tools):
    slot = _slot(
        attempts=[
            {"ts": "2026-05-19T06:00:00+00:00", "target_date": "2026-05-27",
             "outcome": "no_slots", "booking_id": None, "error": None},
            {"ts": "2026-05-20T06:00:00+00:00", "target_date": "2026-05-27",
             "outcome": "booked", "booking_id": "b-9", "error": None},
        ]
    )
    assert tools._summarize(slot) == {
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


def test_summarize_no_attempts(tools: Tools):
    assert tools._summarize(_slot())["last_outcome"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mcp && uv run pytest tests/test_wanted_tools.py -k summarize -v`
Expected: FAIL — `AttributeError: 'Tools' object has no attribute '_summarize'`

- [ ] **Step 3: Add `_summarize` to `Tools`**

Add this method to the `Tools` class in `mcp/src/tee_sniper_mcp/tools.py` (e.g. after `__init__`):

```python
    @staticmethod
    def _summarize(slot: dict[str, Any]) -> dict[str, Any]:
        """Trim a WantedResponse to the fields callers care about."""
        attempts = slot.get("attempts") or []
        last_outcome = attempts[-1]["outcome"] if attempts else None
        return {
            "id": slot["id"],
            "kind": slot["kind"],
            "status": slot["status"],
            "target_date": slot.get("target_date"),
            "day_of_week": slot.get("day_of_week"),
            "end_date": slot.get("end_date"),
            "start_time": slot["start_time"],
            "end_time": slot["end_time"],
            "num_slots": slot["num_slots"],
            "partners": slot.get("partners", []),
            "last_outcome": last_outcome,
        }
```

Also add the `parse_day_of_week` import at the top of `tools.py`:

```python
from tee_sniper_mcp.dates import (
    DateParseError,
    parse_date,
    parse_day_of_week,
    parse_time,
    resolve_window,
)
```

(Replace the existing `from tee_sniper_mcp.dates import ...` line with the block above.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mcp && uv run pytest tests/test_wanted_tools.py -k summarize -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mcp/src/tee_sniper_mcp/tools.py mcp/tests/test_wanted_tools.py
git commit -m "feat(mcp): add _summarize helper and wanted-tools test scaffold"
```

---

### Task 3: `create_one_shot_wanted` tool

**Files:**
- Modify: `mcp/src/tee_sniper_mcp/tools.py`
- Test: `mcp/tests/test_wanted_tools.py`

- [ ] **Step 1: Write the failing tests**

Append to `mcp/tests/test_wanted_tools.py`:

```python
import json


@respx.mock
async def test_create_one_shot_wanted_ok(tools: Tools):
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
    assert body["target_date"] == "2026-05-27"  # today=2026-05-19 (Tue) -> next Wed
    assert body["start_time"] == "15:00"
    assert body["end_time"] == "17:00"
    assert body["num_slots"] == 2
    assert body["partners"] == ["p1"]
    # credentials auto-encrypted, never plaintext
    assert "credentials" in body
    assert body["credentials"] not in ("alice:1234", "")
    assert "1234" not in body["credentials"]


async def test_create_one_shot_wanted_bad_date(tools: Tools):
    result = await tools.create_one_shot_wanted(
        target_date="blursday", start_time="3pm", end_time="5pm"
    )
    assert "error" in result and "blursday" in result["error"]


@respx.mock
async def test_create_one_shot_wanted_surfaces_422(tools: Tools):
    respx.post("http://api.test/api/wanted", params={"kind": "one_shot"}).mock(
        return_value=httpx.Response(422, json={"detail": "end_time must be after start_time"})
    )
    result = await tools.create_one_shot_wanted(
        target_date="tomorrow", start_time="5pm", end_time="3pm"
    )
    assert "error" in result and "end_time must be after start_time" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mcp && uv run pytest tests/test_wanted_tools.py -k create_one_shot -v`
Expected: FAIL — `AttributeError: 'Tools' object has no attribute 'create_one_shot_wanted'`

- [ ] **Step 3: Implement the tool**

Add the `encrypt_credentials` import near the top of `tools.py`:

```python
from tee_sniper_mcp.auth import encrypt_credentials
```

Add a private credential helper and the tool method to the `Tools` class:

```python
    def _credentials(self) -> str:
        return encrypt_credentials(
            self._config.username,
            self._config.pin,
            self._config.shared_secret,
        )

    async def create_one_shot_wanted(
        self,
        target_date: str,
        start_time: str,
        end_time: str,
        num_slots: int = 1,
        partners: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a one-shot wanted tee-time request."""
        try:
            td = parse_date(target_date, today=self._today())
            start = parse_time(start_time)
            end = parse_time(end_time)
        except DateParseError as exc:
            return {"error": str(exc)}

        body = {
            "target_date": td.isoformat(),
            "start_time": start,
            "end_time": end,
            "num_slots": num_slots,
            "partners": partners or [],
            "credentials": self._credentials(),
        }
        try:
            response = await self._api.post(
                "/api/wanted", params={"kind": "one_shot"}, json=body
            )
        except ApiError as exc:
            return {"error": str(exc)}

        try:
            return self._summarize(response)
        except (KeyError, TypeError) as exc:
            return {"error": f"unexpected API response: {exc}"}
```

Note: `ApiClient.post` currently has signature `post(self, path, *, json=None)`. It does **not** accept `params`. Add `params` support — see Step 3b.

- [ ] **Step 3b: Extend `ApiClient.post` to accept `params`**

In `mcp/src/tee_sniper_mcp/api_client.py`, change `post` and `patch` to forward `params`:

```python
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
```

`_request` already accepts and forwards `params`, so no further change is needed there.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd mcp && uv run pytest tests/test_wanted_tools.py -k create_one_shot -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full mcp suite (regression check on api_client change)**

Run: `cd mcp && uv run pytest`
Expected: PASS (existing `test_api_client.py` and `test_tools.py` still green)

- [ ] **Step 6: Commit**

```bash
git add mcp/src/tee_sniper_mcp/tools.py mcp/src/tee_sniper_mcp/api_client.py mcp/tests/test_wanted_tools.py
git commit -m "feat(mcp): add create_one_shot_wanted tool"
```

---

### Task 4: `create_recurring_wanted` tool

**Files:**
- Modify: `mcp/src/tee_sniper_mcp/tools.py`
- Test: `mcp/tests/test_wanted_tools.py`

- [ ] **Step 1: Write the failing tests**

Append to `mcp/tests/test_wanted_tools.py`:

```python
def _recurring_slot(**over) -> dict:
    return _slot(
        kind="recurring",
        target_date=None,
        day_of_week=5,
        end_date="2026-08-01",
        **over,
    )


@respx.mock
async def test_create_recurring_wanted_ok(tools: Tools):
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
    assert "1234" not in body["credentials"]


@respx.mock
async def test_create_recurring_wanted_no_end_date_omits_field(tools: Tools):
    route = respx.post("http://api.test/api/wanted", params={"kind": "recurring"}).mock(
        return_value=httpx.Response(201, json=_recurring_slot(end_date=None))
    )
    await tools.create_recurring_wanted(
        day_of_week="sat", start_time="3pm", end_time="5pm"
    )
    body = json.loads(route.calls.last.request.read())
    assert "end_date" not in body


async def test_create_recurring_wanted_bad_day(tools: Tools):
    result = await tools.create_recurring_wanted(
        day_of_week="funday", start_time="3pm", end_time="5pm"
    )
    assert "error" in result and "funday" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mcp && uv run pytest tests/test_wanted_tools.py -k create_recurring -v`
Expected: FAIL — `AttributeError: 'Tools' object has no attribute 'create_recurring_wanted'`

- [ ] **Step 3: Implement the tool**

Add to the `Tools` class in `tools.py`:

```python
    async def create_recurring_wanted(
        self,
        day_of_week: str | int,
        start_time: str,
        end_time: str,
        num_slots: int = 1,
        partners: list[str] | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Create a recurring wanted tee-time request (one weekday)."""
        try:
            dow = parse_day_of_week(day_of_week)
            start = parse_time(start_time)
            end = parse_time(end_time)
            ed = (
                parse_date(end_date, today=self._today()).isoformat()
                if end_date
                else None
            )
        except DateParseError as exc:
            return {"error": str(exc)}

        body: dict[str, Any] = {
            "day_of_week": dow,
            "start_time": start,
            "end_time": end,
            "num_slots": num_slots,
            "partners": partners or [],
            "credentials": self._credentials(),
        }
        if ed is not None:
            body["end_date"] = ed
        try:
            response = await self._api.post(
                "/api/wanted", params={"kind": "recurring"}, json=body
            )
        except ApiError as exc:
            return {"error": str(exc)}

        try:
            return self._summarize(response)
        except (KeyError, TypeError) as exc:
            return {"error": f"unexpected API response: {exc}"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd mcp && uv run pytest tests/test_wanted_tools.py -k create_recurring -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add mcp/src/tee_sniper_mcp/tools.py mcp/tests/test_wanted_tools.py
git commit -m "feat(mcp): add create_recurring_wanted tool"
```

---

### Task 5: `list_wanted` and `get_wanted` tools

**Files:**
- Modify: `mcp/src/tee_sniper_mcp/tools.py`
- Test: `mcp/tests/test_wanted_tools.py`

- [ ] **Step 1: Write the failing tests**

Append to `mcp/tests/test_wanted_tools.py`:

```python
_VALID_STATUSES = {"pending", "booked", "expired", "disabled"}


@respx.mock
async def test_list_wanted_no_filter(tools: Tools):
    route = respx.get("http://api.test/api/wanted").mock(
        return_value=httpx.Response(200, json=[_slot(), _recurring_slot()])
    )
    result = await tools.list_wanted()
    assert result == {
        "wanted": [tools._summarize(_slot()), tools._summarize(_recurring_slot())]
    }
    assert "status" not in route.calls.last.request.url.params


@respx.mock
async def test_list_wanted_with_status_filter(tools: Tools):
    route = respx.get("http://api.test/api/wanted", params={"status": "booked"}).mock(
        return_value=httpx.Response(200, json=[_slot(status="booked")])
    )
    result = await tools.list_wanted(status="booked")
    assert result["wanted"][0]["status"] == "booked"
    assert route.calls.last.request.url.params["status"] == "booked"


async def test_list_wanted_rejects_bad_status(tools: Tools):
    result = await tools.list_wanted(status="nope")
    assert "error" in result and "nope" in result["error"]


@respx.mock
async def test_get_wanted_returns_full_slot(tools: Tools):
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
async def test_get_wanted_404(tools: Tools):
    respx.get("http://api.test/api/wanted/missing").mock(
        return_value=httpx.Response(404, json={"detail": "Wanted slot not found"})
    )
    result = await tools.get_wanted(wanted_id="missing")
    assert "error" in result and "not found" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mcp && uv run pytest tests/test_wanted_tools.py -k "list_wanted or get_wanted" -v`
Expected: FAIL — `AttributeError: 'Tools' object has no attribute 'list_wanted'`

- [ ] **Step 3: Implement the tools**

Add to the `Tools` class in `tools.py`:

```python
    _WANTED_STATUSES = ("pending", "booked", "expired", "disabled")

    async def list_wanted(self, status: str | None = None) -> dict[str, Any]:
        """List wanted tee-time requests, optionally filtered by status."""
        params: dict[str, str] | None = None
        if status is not None:
            if status not in self._WANTED_STATUSES:
                return {
                    "error": (
                        f"invalid status '{status}'; expected one of "
                        f"{', '.join(self._WANTED_STATUSES)}"
                    )
                }
            params = {"status": status}
        try:
            response = await self._api.get("/api/wanted", params=params)
        except ApiError as exc:
            return {"error": str(exc)}
        try:
            return {"wanted": [self._summarize(s) for s in response]}
        except (KeyError, TypeError) as exc:
            return {"error": f"unexpected API response: {exc}"}

    async def get_wanted(self, wanted_id: str) -> dict[str, Any]:
        """Get a single wanted request, including its full attempt history."""
        try:
            response = await self._api.get(f"/api/wanted/{wanted_id}")
        except ApiError as exc:
            return {"error": str(exc)}
        if not isinstance(response, dict):
            return {"error": f"unexpected API response: {response!r}"}
        return response
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd mcp && uv run pytest tests/test_wanted_tools.py -k "list_wanted or get_wanted" -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add mcp/src/tee_sniper_mcp/tools.py mcp/tests/test_wanted_tools.py
git commit -m "feat(mcp): add list_wanted and get_wanted tools"
```

---

### Task 6: `update_wanted` tool

**Files:**
- Modify: `mcp/src/tee_sniper_mcp/tools.py`
- Test: `mcp/tests/test_wanted_tools.py`

- [ ] **Step 1: Write the failing tests**

Append to `mcp/tests/test_wanted_tools.py`:

```python
@respx.mock
async def test_update_wanted_sends_only_provided_fields(tools: Tools):
    route = respx.patch("http://api.test/api/wanted/w-1").mock(
        return_value=httpx.Response(200, json=_slot(num_slots=3))
    )
    result = await tools.update_wanted(wanted_id="w-1", num_slots=3)
    assert result == tools._summarize(_slot(num_slots=3))
    body = json.loads(route.calls.last.request.read())
    assert body == {"num_slots": 3}


@respx.mock
async def test_update_wanted_parses_times(tools: Tools):
    route = respx.patch("http://api.test/api/wanted/w-1").mock(
        return_value=httpx.Response(200, json=_slot())
    )
    await tools.update_wanted(wanted_id="w-1", start_time="3pm", end_time="5pm")
    body = json.loads(route.calls.last.request.read())
    assert body == {"start_time": "15:00", "end_time": "17:00"}


async def test_update_wanted_no_fields_is_error(tools: Tools):
    result = await tools.update_wanted(wanted_id="w-1")
    assert "error" in result and "no fields" in result["error"].lower()


async def test_update_wanted_bad_time(tools: Tools):
    result = await tools.update_wanted(wanted_id="w-1", start_time="half past noon")
    assert "error" in result


@respx.mock
async def test_update_wanted_404(tools: Tools):
    respx.patch("http://api.test/api/wanted/missing").mock(
        return_value=httpx.Response(404, json={"detail": "Wanted slot not found"})
    )
    result = await tools.update_wanted(wanted_id="missing", num_slots=2)
    assert "error" in result and "not found" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mcp && uv run pytest tests/test_wanted_tools.py -k update_wanted -v`
Expected: FAIL — `AttributeError: 'Tools' object has no attribute 'update_wanted'`

- [ ] **Step 3: Implement the tool**

Add to the `Tools` class in `tools.py`:

```python
    async def update_wanted(
        self,
        wanted_id: str,
        start_time: str | None = None,
        end_time: str | None = None,
        num_slots: int | None = None,
        partners: list[str] | None = None,
    ) -> dict[str, Any]:
        """Edit mutable fields of a wanted request. Only provided fields change."""
        body: dict[str, Any] = {}
        try:
            if start_time is not None:
                body["start_time"] = parse_time(start_time)
            if end_time is not None:
                body["end_time"] = parse_time(end_time)
        except DateParseError as exc:
            return {"error": str(exc)}
        if num_slots is not None:
            body["num_slots"] = num_slots
        if partners is not None:
            body["partners"] = partners

        if not body:
            return {"error": "no fields to update"}

        try:
            response = await self._api.patch(
                f"/api/wanted/{wanted_id}", json=body
            )
        except ApiError as exc:
            return {"error": str(exc)}
        try:
            return self._summarize(response)
        except (KeyError, TypeError) as exc:
            return {"error": f"unexpected API response: {exc}"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd mcp && uv run pytest tests/test_wanted_tools.py -k update_wanted -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add mcp/src/tee_sniper_mcp/tools.py mcp/tests/test_wanted_tools.py
git commit -m "feat(mcp): add update_wanted tool"
```

---

### Task 7: `set_wanted_enabled` and `delete_wanted` tools

**Files:**
- Modify: `mcp/src/tee_sniper_mcp/tools.py`
- Test: `mcp/tests/test_wanted_tools.py`

- [ ] **Step 1: Write the failing tests**

Append to `mcp/tests/test_wanted_tools.py`:

```python
@respx.mock
async def test_set_wanted_enabled_false_sends_disabled_true(tools: Tools):
    route = respx.patch("http://api.test/api/wanted/w-1").mock(
        return_value=httpx.Response(200, json=_slot(status="disabled"))
    )
    result = await tools.set_wanted_enabled(wanted_id="w-1", enabled=False)
    assert result == tools._summarize(_slot(status="disabled"))
    assert json.loads(route.calls.last.request.read()) == {"disabled": True}


@respx.mock
async def test_set_wanted_enabled_true_sends_disabled_false(tools: Tools):
    route = respx.patch("http://api.test/api/wanted/w-1").mock(
        return_value=httpx.Response(200, json=_slot(status="pending"))
    )
    await tools.set_wanted_enabled(wanted_id="w-1", enabled=True)
    assert json.loads(route.calls.last.request.read()) == {"disabled": False}


@respx.mock
async def test_delete_wanted_ok(tools: Tools):
    respx.delete("http://api.test/api/wanted/w-1").mock(
        return_value=httpx.Response(204)
    )
    result = await tools.delete_wanted(wanted_id="w-1")
    assert result == {"deleted": True, "id": "w-1"}


@respx.mock
async def test_delete_wanted_404(tools: Tools):
    respx.delete("http://api.test/api/wanted/missing").mock(
        return_value=httpx.Response(404, json={"detail": "Wanted slot not found"})
    )
    result = await tools.delete_wanted(wanted_id="missing")
    assert "error" in result and "not found" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mcp && uv run pytest tests/test_wanted_tools.py -k "set_wanted_enabled or delete_wanted" -v`
Expected: FAIL — `AttributeError: 'Tools' object has no attribute 'set_wanted_enabled'`

- [ ] **Step 3: Implement the tools**

`ApiClient` has no `delete` method yet — add one. In `mcp/src/tee_sniper_mcp/api_client.py`, add alongside `get`/`post`/`patch`:

```python
    async def delete(self, path: str) -> Any:
        return await self._request("DELETE", path)
```

Add to the `Tools` class in `tools.py`:

```python
    async def set_wanted_enabled(
        self, wanted_id: str, enabled: bool
    ) -> dict[str, Any]:
        """Pause (enabled=False) or resume (enabled=True) a wanted request."""
        try:
            response = await self._api.patch(
                f"/api/wanted/{wanted_id}", json={"disabled": not enabled}
            )
        except ApiError as exc:
            return {"error": str(exc)}
        try:
            return self._summarize(response)
        except (KeyError, TypeError) as exc:
            return {"error": f"unexpected API response: {exc}"}

    async def delete_wanted(self, wanted_id: str) -> dict[str, Any]:
        """Delete a wanted request."""
        try:
            await self._api.delete(f"/api/wanted/{wanted_id}")
        except ApiError as exc:
            return {"error": str(exc)}
        return {"deleted": True, "id": wanted_id}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd mcp && uv run pytest tests/test_wanted_tools.py -k "set_wanted_enabled or delete_wanted" -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add mcp/src/tee_sniper_mcp/tools.py mcp/src/tee_sniper_mcp/api_client.py mcp/tests/test_wanted_tools.py
git commit -m "feat(mcp): add set_wanted_enabled and delete_wanted tools"
```

---

### Task 8: Register the 7 tools in server.py + update smoke test

**Files:**
- Modify: `mcp/src/tee_sniper_mcp/server.py`
- Test: `mcp/tests/test_tools.py`

- [ ] **Step 1: Update the failing smoke test**

In `mcp/tests/test_tools.py`, replace the body of `test_server_registers_all_four_tools` so it asserts the full set (rename the function for clarity):

```python
async def test_server_registers_all_tools() -> None:
    from tee_sniper_mcp.server import build_server

    cfg = Config(
        api_base_url="http://api.test",
        username="u",
        pin="p",
        shared_secret="s",
        time_bands_override=None,
    )

    async with build_server(config=cfg) as mcp:
        registered = await mcp.list_tools()

    names = {t.name for t in registered}
    assert names == {
        "find_tee_times",
        "book_tee_time",
        "list_partners",
        "add_partners",
        "create_one_shot_wanted",
        "create_recurring_wanted",
        "list_wanted",
        "get_wanted",
        "update_wanted",
        "set_wanted_enabled",
        "delete_wanted",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mcp && uv run pytest tests/test_tools.py -k registers_all_tools -v`
Expected: FAIL — assertion error, only the original 4 names registered.

- [ ] **Step 3: Register the new tools and add descriptions**

In `mcp/src/tee_sniper_mcp/server.py`, inside `build_server` after the existing four `mcp.tool(...)` lines, add:

```python
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
```

Add these description constants alongside the existing `_*_DESCRIPTION` strings:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mcp && uv run pytest tests/test_tools.py -k registers_all_tools -v`
Expected: PASS

- [ ] **Step 5: Run the full mcp suite**

Run: `cd mcp && uv run pytest`
Expected: PASS (all tests, all files)

- [ ] **Step 6: Commit**

```bash
git add mcp/src/tee_sniper_mcp/server.py mcp/tests/test_tools.py
git commit -m "feat(mcp): register 7 wanted-tee-time tools"
```

---

### Task 9: Documentation

**Files:**
- Modify: `mcp/README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update `mcp/README.md`**

Add a "Wanted tee-times" subsection to the tool reference documenting all 7 tools, their arguments, and the **0 = Monday … 6 = Sunday** day-of-week convention. Match the format/voice of the existing tool reference entries for the original four tools (read the surrounding section first and mirror its structure — argument lists, examples, time-of-day notes).

- [ ] **Step 2: Update `CLAUDE.md`**

In the "MCP Server (Local)" section, update the sentence "proxies four tools (`find_tee_times`, `book_tee_time`, `list_partners`, `add_partners`)" to also mention the 7 wanted tools, and add a one-line pointer to the spec `docs/superpowers/specs/2026-05-19-wanted-tee-times-mcp-tools-design.md` and this plan in the "MCP Plan History" subsection.

- [ ] **Step 3: Verify docs build/render (sanity)**

Run: `cd mcp && uv run pytest`
Expected: PASS (no test impact; this step confirms nothing was broken by edits in adjacent files).

- [ ] **Step 4: Commit**

```bash
git add mcp/README.md CLAUDE.md
git commit -m "docs(mcp): document wanted-tee-time tools"
```

---

### Final verification

- [ ] Run full suite: `cd mcp && uv run pytest` — all green.
- [ ] Run API suite unaffected (sanity, no api/ changes expected): no action needed unless api/ was touched.
- [ ] Controller (not subagents) pushes the branch and opens a single combined PR titled "Add wanted tee-time MCP tools", linking the spec and plan.

## Notes for the implementer

- **Never plaintext credentials.** The create tools must call `self._credentials()` (which calls `encrypt_credentials`). Tests assert the PIN string is absent from the request body — keep it that way.
- **`ApiClient` signature changes** in Tasks 3 and 7 (`params=` on post/patch, new `delete`) are load-bearing for later tasks. Run the full suite after Task 3 to catch regressions early.
- **Out of scope (do not add):** SMS `notify`, per-call credential override, editing kind/target_date/day_of_week. These are deliberately excluded per the spec.
- **Day-of-week is 0=Monday.** Verified against `api/app/services/scheduling.py`. Do not "fix" it to 0=Sunday.
