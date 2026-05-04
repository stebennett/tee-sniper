# Local MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a stdio MCP server (under `mcp/`, run via `uv`) that exposes `find_tee_times`, `book_tee_time`, `list_partners`, and `add_partners` to LLM clients, talking exclusively to the existing FastAPI service.

**Architecture:** A new top-level `mcp/` Python project using FastMCP and httpx. It encrypts credentials locally with the same AES-256-GCM scheme as `api/`, lazily logs in against `/api/login`, caches the bearer token in memory, and proxies four tools to existing REST endpoints plus one new `GET /api/partners` endpoint backed by a JSON config file.

**Tech Stack:** Python 3.14, `uv`, FastMCP ≥ 3.1, httpx, python-dateutil, cryptography (AES-GCM), pytest + respx. CI on GitHub Actions; release artefact is a Docker image on GHCR.

**Spec:** `docs/superpowers/specs/2026-05-03-local-mcp-server-design.md`

**PR / phase workflow:** Per `CLAUDE.md`, each phase ships in its own PR. Phase B can run in parallel with Phase A review; C depends on B; D depends on C; E depends on A + C. Within a phase, follow TDD and commit after each task.

---

## Phase A — `GET /api/partners` endpoint

**Branch:** `mcp/phaseA-partners-endpoint`

### Task A1: Add `partners_file` setting

**Files:**
- Modify: `api/app/config.py`

- [ ] **Step 1: Add the setting**

Edit `api/app/config.py`, after the `base_url: str` line, add:

```python
    # Path to JSON file mapping partner IDs to display names.
    # Format: {"id1": "Alice Smith", "id2": "Bob Jones"}
    partners_file: str | None = None
```

- [ ] **Step 2: Run config tests**

Run: `cd api && .venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS (existing tests should be unaffected; the new field is optional).

- [ ] **Step 3: Commit**

```bash
git add api/app/config.py
git commit -m "Add partners_file setting"
```

### Task A2: Partners loader service (TDD)

**Files:**
- Create: `api/app/services/partners.py`
- Create: `api/tests/test_partners_service.py`

- [ ] **Step 1: Write the failing tests**

Create `api/tests/test_partners_service.py`:

```python
"""Tests for the partners loader service."""

import json
from pathlib import Path

import pytest

from app.services.partners import PartnersService


def test_load_returns_empty_when_path_is_none() -> None:
    service = PartnersService(None)
    assert service.load() == []


def test_load_returns_empty_when_file_missing(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    missing = tmp_path / "missing.json"
    service = PartnersService(str(missing))
    with caplog.at_level("WARNING"):
        result = service.load()
    assert result == []
    assert any("partners file" in r.message.lower() for r in caplog.records)


def test_load_returns_empty_when_file_invalid_json(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    service = PartnersService(str(bad))
    with caplog.at_level("WARNING"):
        result = service.load()
    assert result == []


def test_load_returns_partners_sorted_by_name(tmp_path: Path) -> None:
    f = tmp_path / "partners.json"
    f.write_text(json.dumps({"id2": "Bob Jones", "id1": "Alice Smith"}))
    service = PartnersService(str(f))
    result = service.load()
    assert result == [
        {"id": "id1", "name": "Alice Smith"},
        {"id": "id2", "name": "Bob Jones"},
    ]


def test_load_skips_non_string_values(tmp_path: Path) -> None:
    f = tmp_path / "partners.json"
    f.write_text(json.dumps({"id1": "Alice", "id2": 42, "id3": None}))
    service = PartnersService(str(f))
    result = service.load()
    assert result == [{"id": "id1", "name": "Alice"}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && .venv/bin/python -m pytest tests/test_partners_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.partners'`.

- [ ] **Step 3: Implement the service**

Create `api/app/services/partners.py`:

```python
"""Loader for the configured partners file."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PartnersService:
    """Loads {id: name} partner mappings from a JSON file path."""

    def __init__(self, file_path: str | None) -> None:
        self._file_path = file_path

    def load(self) -> list[dict[str, str]]:
        """Return partners as [{"id": ..., "name": ...}, ...] sorted by name.

        Returns an empty list (and logs a warning) if the path is unset,
        the file is missing, or the file is malformed.
        """
        if not self._file_path:
            return []

        path = Path(self._file_path)
        if not path.is_file():
            logger.warning("Partners file not found at %s", self._file_path)
            return []

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read partners file %s: %s", self._file_path, exc)
            return []

        if not isinstance(raw, dict):
            logger.warning("Partners file %s is not a JSON object", self._file_path)
            return []

        partners = [
            {"id": str(pid), "name": name}
            for pid, name in raw.items()
            if isinstance(name, str)
        ]
        partners.sort(key=lambda p: p["name"])
        return partners
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd api && .venv/bin/python -m pytest tests/test_partners_service.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add api/app/services/partners.py api/tests/test_partners_service.py
git commit -m "Add PartnersService for loading partner config"
```

### Task A3: Response model + DI provider

**Files:**
- Modify: `api/app/models/responses.py`
- Modify: `api/app/dependencies.py`

- [ ] **Step 1: Add response models**

In `api/app/models/responses.py`, after `AddPartnersResponse`, add:

```python
class PartnerResponse(BaseModel):
    """A configured playing partner."""

    id: str = Field(..., description="Partner identifier used by the booking site")
    name: str = Field(..., description="Human-readable partner name")


class PartnersListResponse(BaseModel):
    """Response listing configured playing partners."""

    partners: list[PartnerResponse] = Field(..., description="Configured partners, sorted by name")
```

- [ ] **Step 2: Add DI provider**

In `api/app/dependencies.py`, after `get_encryption_service`, add:

```python
@lru_cache
def get_partners_service() -> "PartnersService":
    """Get cached PartnersService instance."""
    from app.services.partners import PartnersService

    settings = get_settings()
    return PartnersService(settings.partners_file)
```

- [ ] **Step 3: Run existing tests**

Run: `cd api && .venv/bin/python -m pytest -v`
Expected: PASS (no regressions).

- [ ] **Step 4: Commit**

```bash
git add api/app/models/responses.py api/app/dependencies.py
git commit -m "Add PartnersListResponse model and DI provider"
```

### Task A4: `GET /api/partners` route (TDD)

**Files:**
- Modify: `api/app/routers/booking.py`
- Modify: `api/tests/test_booking_routes.py`

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/test_booking_routes.py`:

```python
class TestPartnersEndpoint:
    """Tests for GET /api/partners."""

    def test_returns_partners_list_when_authed(
        self,
        app_and_client: tuple,
        authed_client: tuple,
        tmp_path,
    ) -> None:
        from app.dependencies import get_partners_service
        from app.services.partners import PartnersService

        app, client, _token = authed_client
        f = tmp_path / "partners.json"
        f.write_text('{"id1": "Alice", "id2": "Bob"}')
        app.dependency_overrides[get_partners_service] = lambda: PartnersService(str(f))

        try:
            response = client.get(
                "/api/partners",
                headers={"Authorization": f"Bearer {_token}"},
            )
        finally:
            app.dependency_overrides.pop(get_partners_service, None)

        assert response.status_code == 200
        body = response.json()
        assert body == {
            "partners": [
                {"id": "id1", "name": "Alice"},
                {"id": "id2", "name": "Bob"},
            ]
        }

    def test_returns_empty_when_no_file_configured(
        self,
        app_and_client: tuple,
        authed_client: tuple,
    ) -> None:
        from app.dependencies import get_partners_service
        from app.services.partners import PartnersService

        app, client, _token = authed_client
        app.dependency_overrides[get_partners_service] = lambda: PartnersService(None)

        try:
            response = client.get(
                "/api/partners",
                headers={"Authorization": f"Bearer {_token}"},
            )
        finally:
            app.dependency_overrides.pop(get_partners_service, None)

        assert response.status_code == 200
        assert response.json() == {"partners": []}

    def test_requires_auth(self, app_and_client: tuple) -> None:
        _app, client = app_and_client
        response = client.get("/api/partners")
        assert response.status_code == 403  # FastAPI HTTPBearer returns 403 when missing
```

> **Note:** the existing `authed_client` fixture (defined earlier in this test file) returns `(app, client, token)`. Reuse the same shape; do not redefine the fixture.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && .venv/bin/python -m pytest tests/test_booking_routes.py::TestPartnersEndpoint -v`
Expected: FAIL with 404 on the GET — endpoint does not exist yet.

- [ ] **Step 3: Implement the route**

In `api/app/routers/booking.py`:

a. Add to existing imports:

```python
from app.dependencies import (
    get_booking_client,
    get_current_session,
    get_encryption_service,
    get_partners_service,
    get_session_manager,
    get_settings_dependency,
)
from app.models.responses import (
    AddPartnersResponse,
    AvailabilityResponse,
    BookResponse,
    ErrorResponse,
    LoginResponse,
    PartnerResponse,
    PartnersListResponse,
    TimeSlotResponse,
)
from app.services.partners import PartnersService
```

b. Append a new route at the bottom of the file:

```python
@router.get(
    "/partners",
    response_model=PartnersListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired session"},
    },
)
async def list_partners(
    _session: dict = Depends(get_current_session),
    partners: PartnersService = Depends(get_partners_service),
) -> PartnersListResponse:
    """List configured playing partners (id → name)."""
    return PartnersListResponse(
        partners=[PartnerResponse(**p) for p in partners.load()],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd api && .venv/bin/python -m pytest tests/test_booking_routes.py::TestPartnersEndpoint -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run full API test suite**

Run: `cd api && .venv/bin/python -m pytest -v`
Expected: PASS (no regressions).

- [ ] **Step 6: Commit & open PR**

```bash
git add api/app/routers/booking.py api/tests/test_booking_routes.py
git commit -m "Add GET /api/partners endpoint"
git push -u origin mcp/phaseA-partners-endpoint
gh pr create --title "Add GET /api/partners endpoint" --body "Implements Phase A of docs/superpowers/plans/2026-05-04-local-mcp-server.md. Adds TSA_PARTNERS_FILE config and a new authed endpoint that returns the configured id→name partner mapping."
```

---

## Phase B — MCP scaffold (config, auth, api client, dates)

**Branch:** `mcp/phaseB-scaffold`

### Task B1: Project skeleton

**Files:**
- Create: `mcp/pyproject.toml`
- Create: `mcp/src/tee_sniper_mcp/__init__.py`
- Create: `mcp/.python-version`
- Create: `mcp/README.md` (stub — fleshed out in Phase E)

- [ ] **Step 1: Create `mcp/pyproject.toml`**

```toml
[project]
name = "tee-sniper-mcp"
version = "0.1.0"
description = "Local MCP server that exposes tee-sniper booking operations to LLM clients."
requires-python = ">=3.14"
readme = "README.md"
dependencies = [
    "fastmcp>=3.1.0",
    "httpx>=0.27",
    "python-dateutil>=2.9",
    "cryptography>=43",
]

[project.scripts]
tee-sniper-mcp = "tee_sniper_mcp.server:main"

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "respx>=0.21",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/tee_sniper_mcp"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create the package marker**

Create `mcp/src/tee_sniper_mcp/__init__.py`:

```python
"""Local stdio MCP server for tee-sniper."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create `mcp/.python-version`**

```
3.14
```

- [ ] **Step 4: Create stub README**

Create `mcp/README.md`:

```markdown
# tee-sniper-mcp

Local stdio MCP server that exposes tee-sniper booking operations to LLM clients.

Full documentation lands in Phase E (`docs/superpowers/plans/2026-05-04-local-mcp-server.md`).
```

- [ ] **Step 5: Verify `uv sync` works**

Run: `cd mcp && uv sync --all-extras`
Expected: creates `mcp/.venv/`, resolves and installs dependencies, no errors.

- [ ] **Step 6: Commit**

```bash
git add mcp/
git commit -m "Scaffold mcp/ Python project with uv"
```

### Task B2: Config loader (TDD)

**Files:**
- Create: `mcp/src/tee_sniper_mcp/config.py`
- Create: `mcp/tests/__init__.py`
- Create: `mcp/tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Create `mcp/tests/__init__.py` (empty file).

Create `mcp/tests/test_config.py`:

```python
"""Tests for config loading."""

import json

import pytest

from tee_sniper_mcp.config import Config, ConfigError, load_config


def test_load_config_reads_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TSA_API_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("TSA_USERNAME", "alice")
    monkeypatch.setenv("TSA_PIN", "1234")
    monkeypatch.setenv("TSA_SHARED_SECRET", "s3cret")
    monkeypatch.delenv("TSA_TIME_BANDS", raising=False)

    cfg = load_config()

    assert cfg == Config(
        api_base_url="http://localhost:8000",
        username="alice",
        pin="1234",
        shared_secret="s3cret",
        time_bands_override=None,
    )


def test_load_config_strips_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TSA_API_BASE_URL", "http://localhost:8000/")
    monkeypatch.setenv("TSA_USERNAME", "alice")
    monkeypatch.setenv("TSA_PIN", "1234")
    monkeypatch.setenv("TSA_SHARED_SECRET", "s3cret")

    cfg = load_config()
    assert cfg.api_base_url == "http://localhost:8000"


def test_load_config_parses_time_bands_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TSA_API_BASE_URL", "http://x")
    monkeypatch.setenv("TSA_USERNAME", "u")
    monkeypatch.setenv("TSA_PIN", "p")
    monkeypatch.setenv("TSA_SHARED_SECRET", "s")
    monkeypatch.setenv("TSA_TIME_BANDS", json.dumps({"morning": ["07:00", "11:00"]}))

    cfg = load_config()
    assert cfg.time_bands_override == {"morning": ["07:00", "11:00"]}


def test_load_config_raises_when_missing_required(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("TSA_API_BASE_URL", "TSA_USERNAME", "TSA_PIN", "TSA_SHARED_SECRET"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(ConfigError, match="TSA_API_BASE_URL"):
        load_config()


def test_load_config_raises_on_invalid_time_bands_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TSA_API_BASE_URL", "http://x")
    monkeypatch.setenv("TSA_USERNAME", "u")
    monkeypatch.setenv("TSA_PIN", "p")
    monkeypatch.setenv("TSA_SHARED_SECRET", "s")
    monkeypatch.setenv("TSA_TIME_BANDS", "{not json")

    with pytest.raises(ConfigError, match="TSA_TIME_BANDS"):
        load_config()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mcp && uv run pytest tests/test_config.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `config.py`**

Create `mcp/src/tee_sniper_mcp/config.py`:

```python
"""Environment-based configuration for the MCP server."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    """Validated server configuration."""

    api_base_url: str
    username: str
    pin: str
    shared_secret: str
    time_bands_override: dict[str, list[str]] | None


_REQUIRED = (
    "TSA_API_BASE_URL",
    "TSA_USERNAME",
    "TSA_PIN",
    "TSA_SHARED_SECRET",
)


def load_config() -> Config:
    """Load configuration from environment, raising ConfigError on problems."""
    missing = [name for name in _REQUIRED if not os.environ.get(name)]
    if missing:
        raise ConfigError(f"Missing required env vars: {', '.join(missing)}")

    bands_raw = os.environ.get("TSA_TIME_BANDS")
    bands_override: dict[str, list[str]] | None = None
    if bands_raw:
        try:
            parsed = json.loads(bands_raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"TSA_TIME_BANDS is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ConfigError("TSA_TIME_BANDS must be a JSON object")
        bands_override = parsed

    return Config(
        api_base_url=os.environ["TSA_API_BASE_URL"].rstrip("/"),
        username=os.environ["TSA_USERNAME"],
        pin=os.environ["TSA_PIN"],
        shared_secret=os.environ["TSA_SHARED_SECRET"],
        time_bands_override=bands_override,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd mcp && uv run pytest tests/test_config.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add mcp/src/tee_sniper_mcp/config.py mcp/tests/__init__.py mcp/tests/test_config.py
git commit -m "Add MCP config loader"
```

### Task B3: Date / time / band parsing (TDD)

**Files:**
- Create: `mcp/src/tee_sniper_mcp/dates.py`
- Create: `mcp/tests/test_dates.py`

- [ ] **Step 1: Write the failing tests**

Create `mcp/tests/test_dates.py`:

```python
"""Tests for date / time / band parsing."""

import datetime as dt

import pytest

from tee_sniper_mcp.dates import (
    DateParseError,
    DEFAULT_BANDS,
    parse_date,
    parse_time,
    resolve_band,
    resolve_window,
)


@pytest.fixture
def today() -> dt.date:
    return dt.date(2026, 5, 4)  # a Monday


def test_parse_date_iso(today: dt.date) -> None:
    assert parse_date("2026-06-01", today=today) == dt.date(2026, 6, 1)


def test_parse_date_today(today: dt.date) -> None:
    assert parse_date("today", today=today) == today


def test_parse_date_tomorrow(today: dt.date) -> None:
    assert parse_date("Tomorrow", today=today) == dt.date(2026, 5, 5)


def test_parse_date_in_n_days(today: dt.date) -> None:
    assert parse_date("in 3 days", today=today) == dt.date(2026, 5, 7)


def test_parse_date_next_weekday(today: dt.date) -> None:
    # today=Mon 2026-05-04, "next saturday" => 2026-05-09
    assert parse_date("next saturday", today=today) == dt.date(2026, 5, 9)


def test_parse_date_this_weekday_future(today: dt.date) -> None:
    # today=Mon 2026-05-04, "this friday" => 2026-05-08
    assert parse_date("this friday", today=today) == dt.date(2026, 5, 8)


def test_parse_date_invalid_raises(today: dt.date) -> None:
    with pytest.raises(DateParseError):
        parse_date("blursday", today=today)


def test_parse_time_hhmm() -> None:
    assert parse_time("15:00") == "15:00"


def test_parse_time_3pm() -> None:
    assert parse_time("3pm") == "15:00"


def test_parse_time_3_30_pm() -> None:
    assert parse_time("3:30 PM") == "15:30"


def test_parse_time_invalid_raises() -> None:
    with pytest.raises(DateParseError):
        parse_time("teatime")


def test_resolve_band_default() -> None:
    assert resolve_band("early_morning") == ("06:00", "09:00")


def test_resolve_band_all_day_returns_none() -> None:
    assert resolve_band("all_day") == (None, None)


def test_resolve_band_unknown_raises() -> None:
    with pytest.raises(DateParseError):
        resolve_band("nightowl")


def test_resolve_band_with_override() -> None:
    override = {"morning": ["07:00", "11:00"]}
    assert resolve_band("morning", override=override) == ("07:00", "11:00")


def test_resolve_window_explicit_wins_over_band() -> None:
    start, end = resolve_window(start_time="08:30", end_time=None, time_of_day="afternoon")
    assert start == "08:30"
    assert end is None


def test_resolve_window_band_used_when_no_explicit() -> None:
    start, end = resolve_window(start_time=None, end_time=None, time_of_day="morning")
    assert (start, end) == DEFAULT_BANDS["morning"]


def test_resolve_window_no_filter() -> None:
    assert resolve_window(start_time=None, end_time=None, time_of_day=None) == (None, None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mcp && uv run pytest tests/test_dates.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `dates.py`**

Create `mcp/src/tee_sniper_mcp/dates.py`:

```python
"""Date, time, and time-of-day band parsing."""

from __future__ import annotations

import datetime as dt
import re
from typing import Mapping

from dateutil import parser as du_parser


class DateParseError(ValueError):
    """Raised when a date, time, or band cannot be parsed."""


DEFAULT_BANDS: Mapping[str, tuple[str | None, str | None]] = {
    "early_morning": ("06:00", "09:00"),
    "morning": ("09:00", "12:00"),
    "midday": ("11:00", "14:00"),
    "afternoon": ("12:00", "17:00"),
    "early_evening": ("17:00", "19:00"),
    "all_day": (None, None),
}

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def parse_date(value: str, *, today: dt.date | None = None) -> dt.date:
    """Parse a relative or absolute date string into a date."""
    if today is None:
        today = dt.date.today()
    s = value.strip().lower()

    if not s:
        raise DateParseError("empty date")

    if s == "today":
        return today
    if s == "tomorrow":
        return today + dt.timedelta(days=1)
    if s == "yesterday":
        return today - dt.timedelta(days=1)

    m = re.fullmatch(r"in (\d+) days?", s)
    if m:
        return today + dt.timedelta(days=int(m.group(1)))

    m = re.fullmatch(r"(this|next) ([a-z]+)", s)
    if m:
        qualifier, weekday = m.group(1), m.group(2)
        if weekday not in _WEEKDAYS:
            raise DateParseError(f"unknown weekday in '{value}'")
        target = _WEEKDAYS[weekday]
        delta = (target - today.weekday()) % 7
        if qualifier == "next" and delta == 0:
            delta = 7
        if qualifier == "this" and delta == 0:
            return today
        return today + dt.timedelta(days=delta)

    try:
        parsed = du_parser.parse(value, default=dt.datetime.combine(today, dt.time()))
    except (ValueError, OverflowError) as exc:
        raise DateParseError(f"could not parse date '{value}'") from exc
    return parsed.date()


def parse_time(value: str) -> str:
    """Parse a time string into 'HH:MM' 24-hour format."""
    s = value.strip()
    if not s:
        raise DateParseError("empty time")
    try:
        parsed = du_parser.parse(s)
    except (ValueError, OverflowError) as exc:
        raise DateParseError(f"could not parse time '{value}'") from exc
    return parsed.strftime("%H:%M")


def resolve_band(
    name: str,
    *,
    override: Mapping[str, list[str]] | None = None,
) -> tuple[str | None, str | None]:
    """Resolve a named time-of-day band to a (start, end) tuple."""
    if override and name in override:
        pair = override[name]
        if len(pair) != 2:
            raise DateParseError(f"override for band '{name}' must be [start, end]")
        return (pair[0] or None, pair[1] or None)
    if name not in DEFAULT_BANDS:
        raise DateParseError(f"unknown time_of_day band '{name}'")
    return DEFAULT_BANDS[name]


def resolve_window(
    *,
    start_time: str | None,
    end_time: str | None,
    time_of_day: str | None,
    bands_override: Mapping[str, list[str]] | None = None,
) -> tuple[str | None, str | None]:
    """Resolve final (start, end) window for a find_tee_times call."""
    if start_time or end_time:
        return (
            parse_time(start_time) if start_time else None,
            parse_time(end_time) if end_time else None,
        )
    if time_of_day:
        return resolve_band(time_of_day, override=bands_override)
    return (None, None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd mcp && uv run pytest tests/test_dates.py -v`
Expected: PASS (16 tests).

- [ ] **Step 5: Commit**

```bash
git add mcp/src/tee_sniper_mcp/dates.py mcp/tests/test_dates.py
git commit -m "Add date/time/band parsing"
```

### Task B4: Auth manager (TDD)

**Files:**
- Create: `mcp/src/tee_sniper_mcp/auth.py`
- Create: `mcp/tests/test_auth.py`

- [ ] **Step 1: Write the failing tests**

Create `mcp/tests/test_auth.py`:

```python
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
```

> **Note:** the roundtrip test imports the API package. Add `mcp/conftest.py` to make it importable in CI (next sub-step).

- [ ] **Step 2: Add conftest to expose the API package for the roundtrip test**

Create `mcp/conftest.py`:

```python
"""Test bootstrap: expose api/app on sys.path for cross-process roundtrip tests."""

import sys
from pathlib import Path

_API_SRC = Path(__file__).resolve().parent.parent / "api"
if _API_SRC.is_dir():
    sys.path.insert(0, str(_API_SRC))
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd mcp && uv run pytest tests/test_auth.py -v`
Expected: FAIL — `tee_sniper_mcp.auth` does not exist.

- [ ] **Step 4: Implement `auth.py`**

Create `mcp/src/tee_sniper_mcp/auth.py`:

```python
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
        self._token = body["access_token"]
        self._expires_at = dt.datetime.fromisoformat(body["expires_at"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd mcp && uv run pytest tests/test_auth.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add mcp/src/tee_sniper_mcp/auth.py mcp/tests/test_auth.py mcp/conftest.py
git commit -m "Add AuthManager with AES-GCM credential encryption"
```

### Task B5: API client wrapper (TDD)

**Files:**
- Create: `mcp/src/tee_sniper_mcp/api_client.py`
- Create: `mcp/tests/test_api_client.py`

- [ ] **Step 1: Write the failing tests**

Create `mcp/tests/test_api_client.py`:

```python
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
    assert book.calls.last.request.read() == b'{"num_slots": 2, "dry_run": false}'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mcp && uv run pytest tests/test_api_client.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `api_client.py`**

Create `mcp/src/tee_sniper_mcp/api_client.py`:

```python
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

    async def post(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        return await self._request("POST", path, json=json)

    async def patch(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        return await self._request("PATCH", path, json=json)

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
            return response.json().get("detail", response.text)
        except ValueError:
            return response.text or response.reason_phrase
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd mcp && uv run pytest tests/test_api_client.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run full mcp test suite**

Run: `cd mcp && uv run pytest -v`
Expected: PASS (all phase B tests green).

- [ ] **Step 6: Commit & open PR**

```bash
git add mcp/src/tee_sniper_mcp/api_client.py mcp/tests/test_api_client.py
git commit -m "Add ApiClient with bearer auth and 401 retry"
git push -u origin mcp/phaseB-scaffold
gh pr create --title "Scaffold mcp/ Python project (config, dates, auth, api_client)" --body "Phase B of docs/superpowers/plans/2026-05-04-local-mcp-server.md. Sets up the uv-managed mcp/ project with config loading, date/time/band parsing, AES-GCM credential encryption + lazy login, and an authenticated REST API client. No tools wired yet — Phase C builds those on top."
```

---

## Phase C — MCP tools and server entrypoint

**Branch:** `mcp/phaseC-tools` (depends on Phase A + B merged into main)

### Task C1: Tool implementations (TDD)

**Files:**
- Create: `mcp/src/tee_sniper_mcp/tools.py`
- Create: `mcp/tests/test_tools.py`

- [ ] **Step 1: Write the failing tests**

Create `mcp/tests/test_tools.py`:

```python
"""Tests for the four MCP tools."""

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
    async with httpx.AsyncClient() as http:
        respx.post("http://api.test/api/login").mock(return_value=_login_response())
        api = ApiClient(config, AuthManager(config, http), http)
        yield Tools(config=config, api=api, today=lambda: dt.date(2026, 5, 4))


@respx.mock
async def test_find_tee_times_with_band(tools: Tools) -> None:
    route = respx.get("http://api.test/api/2026-05-05/times").mock(
        return_value=httpx.Response(
            200,
            json={
                "date": "2026-05-05",
                "times": [
                    {"time": "07:00", "can_book": True, "booking_form": {"slot": "1"}},
                    {"time": "08:00", "can_book": False, "booking_form": {}},
                ],
                "filtered_count": 2,
                "total_count": 5,
            },
        )
    )

    result = await tools.find_tee_times(date="tomorrow", time_of_day="early_morning")

    assert result == {
        "date": "2026-05-05",
        "slots": [{"time": "07:00", "can_book": True}, {"time": "08:00", "can_book": False}],
    }
    qs = route.calls.last.request.url.params
    assert qs["start"] == "06:00"
    assert qs["end"] == "09:00"


@respx.mock
async def test_find_tee_times_explicit_times_override_band(tools: Tools) -> None:
    route = respx.get("http://api.test/api/2026-05-05/times").mock(
        return_value=httpx.Response(
            200,
            json={"date": "2026-05-05", "times": [], "filtered_count": 0, "total_count": 0},
        )
    )

    await tools.find_tee_times(
        date="tomorrow",
        start_time="3pm",
        end_time="5pm",
        time_of_day="early_morning",
    )

    qs = route.calls.last.request.url.params
    assert qs["start"] == "15:00"
    assert qs["end"] == "17:00"


async def test_find_tee_times_invalid_date_returns_error(tools: Tools) -> None:
    result = await tools.find_tee_times(date="blursday")
    assert "error" in result
    assert "blursday" in result["error"]


@respx.mock
async def test_book_tee_time_passes_through(tools: Tools) -> None:
    route = respx.post("http://api.test/api/2026-05-05/time/08:00/book").mock(
        return_value=httpx.Response(
            200,
            json={
                "booking_id": "b-1",
                "date": "2026-05-05",
                "time": "08:00",
                "slots_booked": 2,
                "message": "ok",
            },
        )
    )

    result = await tools.book_tee_time(date="tomorrow", time="8am", num_slots=2)

    assert result == {
        "booking_id": "b-1",
        "date": "2026-05-05",
        "time": "08:00",
        "num_slots": 2,
        "dry_run": False,
    }
    body = route.calls.last.request.read()
    assert b'"num_slots": 2' in body
    assert b'"dry_run": false' in body


@respx.mock
async def test_list_partners_normalises_response(tools: Tools) -> None:
    respx.get("http://api.test/api/partners").mock(
        return_value=httpx.Response(
            200, json={"partners": [{"id": "id1", "name": "Alice"}, {"id": "id2", "name": "Bob"}]}
        )
    )

    result = await tools.list_partners()

    assert result == {"partners": [{"id": "id1", "name": "Alice"}, {"id": "id2", "name": "Bob"}]}


@respx.mock
async def test_add_partners_passes_through(tools: Tools) -> None:
    route = respx.patch("http://api.test/api/bookings/b-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "booking_id": "b-1",
                "partners_added": ["id1", "id2"],
                "partners_failed": [],
                "message": "ok",
            },
        )
    )

    result = await tools.add_partners(booking_id="b-1", partner_ids=["id1", "id2"])

    assert result == {
        "booking_id": "b-1",
        "partners_added": ["id1", "id2"],
        "partners_failed": [],
    }
    body = route.calls.last.request.read()
    assert b'"partners": ["id1", "id2"]' in body


@respx.mock
async def test_api_error_surfaces_as_error_dict(tools: Tools) -> None:
    respx.get("http://api.test/api/2026-05-05/times").mock(
        return_value=httpx.Response(502, json={"detail": "upstream broken"})
    )

    result = await tools.find_tee_times(date="tomorrow")

    assert "error" in result
    assert "upstream broken" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd mcp && uv run pytest tests/test_tools.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `tools.py`**

Create `mcp/src/tee_sniper_mcp/tools.py`:

```python
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

        slots = [
            {"time": slot["time"], "can_book": slot["can_book"]}
            for slot in response.get("times", [])
        ]
        return {"date": response["date"], "slots": slots}

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

        return {
            "booking_id": response["booking_id"],
            "date": response["date"],
            "time": response["time"],
            "num_slots": response["slots_booked"],
            "dry_run": dry_run,
        }

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

        return {
            "booking_id": response["booking_id"],
            "partners_added": response.get("partners_added", []),
            "partners_failed": response.get("partners_failed", []),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd mcp && uv run pytest tests/test_tools.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add mcp/src/tee_sniper_mcp/tools.py mcp/tests/test_tools.py
git commit -m "Add MCP tool implementations"
```

### Task C2: FastMCP server + entrypoint

**Files:**
- Create: `mcp/src/tee_sniper_mcp/server.py`
- Modify: `mcp/tests/test_tools.py` (add server smoke test)

- [ ] **Step 1: Add a smoke test for tool registration**

Append to `mcp/tests/test_tools.py`:

```python
async def test_server_registers_all_four_tools() -> None:
    from tee_sniper_mcp.server import build_server

    # Build with stub config (no env mutation needed because we pass it directly).
    cfg = Config(
        api_base_url="http://api.test",
        username="u",
        pin="p",
        shared_secret="s",
        time_bands_override=None,
    )

    async with build_server(config=cfg) as mcp:
        registered = await mcp.get_tools()

    names = {t.name for t in registered}
    assert names == {"find_tee_times", "book_tee_time", "list_partners", "add_partners"}
```

> **Note:** `build_server` is an async context manager that yields a configured `FastMCP` instance and cleans up the underlying `httpx.AsyncClient`. The exact FastMCP introspection method (`get_tools`) is from FastMCP ≥ 3.1; if the API differs in the resolved version, fall back to listing via `await mcp.list_tools()` (the failing test will tell you which to use).

- [ ] **Step 2: Run the smoke test to confirm it fails**

Run: `cd mcp && uv run pytest tests/test_tools.py::test_server_registers_all_four_tools -v`
Expected: FAIL — `tee_sniper_mcp.server` does not exist.

- [ ] **Step 3: Implement `server.py`**

Create `mcp/src/tee_sniper_mcp/server.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `cd mcp && uv run pytest -v`
Expected: PASS. If `mcp.get_tools()` is unavailable in the installed FastMCP version, switch the smoke test to whichever introspection helper exists (`list_tools`, `_tool_manager`, etc.) — the assertion remains the same set of four names.

- [ ] **Step 5: Manual smoke test (optional but recommended)**

With the API running locally and env vars set:

```bash
cd mcp
TSA_API_BASE_URL=http://localhost:8000 \
TSA_USERNAME=... TSA_PIN=... TSA_SHARED_SECRET=... \
uv run tee-sniper-mcp <<< '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Expected: a JSON-RPC response listing the four tools.

- [ ] **Step 6: Commit & open PR**

```bash
git add mcp/src/tee_sniper_mcp/server.py mcp/tests/test_tools.py
git commit -m "Add FastMCP server entrypoint"
git push -u origin mcp/phaseC-tools
gh pr create --title "Implement MCP tools and server entrypoint" --body "Phase C of docs/superpowers/plans/2026-05-04-local-mcp-server.md. Wires the four tools (find_tee_times, book_tee_time, list_partners, add_partners) onto a FastMCP stdio server. Server is end-to-end runnable via uv run tee-sniper-mcp."
```

---

## Phase D — Docker image and CI/CD

**Branch:** `mcp/phaseD-docker-ci`

### Task D1: `mcp/Dockerfile`

**Files:**
- Create: `mcp/Dockerfile`
- Create: `mcp/.dockerignore`

- [ ] **Step 1: Create the Dockerfile**

Create `mcp/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.14-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install .

USER 65532:65532

ENTRYPOINT ["tee-sniper-mcp"]
```

- [ ] **Step 2: Create `.dockerignore`**

Create `mcp/.dockerignore`:

```
.venv
.python-version
tests
conftest.py
**/__pycache__
*.egg-info
```

- [ ] **Step 3: Build the image locally**

Run: `cd mcp && docker build -t tee-sniper-mcp:dev .`
Expected: image builds successfully.

- [ ] **Step 4: Smoke-test the image runs**

Run:
```bash
docker run --rm tee-sniper-mcp:dev --help 2>&1 | head -5 || true
# tee-sniper-mcp doesn't expose --help; the run should fail cleanly with a config error message:
docker run --rm tee-sniper-mcp:dev
```

Expected: process exits non-zero with `tee-sniper-mcp: configuration error: Missing required env vars: ...` on stderr.

- [ ] **Step 5: Commit**

```bash
git add mcp/Dockerfile mcp/.dockerignore
git commit -m "Add Dockerfile for tee-sniper-mcp"
```

### Task D2: PR build workflow

**Files:**
- Create: `.github/workflows/mcp-build.yml`

- [ ] **Step 1: Create the workflow**

Create `.github/workflows/mcp-build.yml`:

```yaml
name: MCP Build and Test

on:
  push:
    branches: [main]
    paths:
      - 'mcp/**'
      - '.github/workflows/mcp-build.yml'
  pull_request:
    branches: [main]
    paths:
      - 'mcp/**'
      - '.github/workflows/mcp-build.yml'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: '3.14'

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Sync dependencies
        run: |
          cd mcp
          uv sync --all-extras --dev

      - name: Run tests
        run: |
          cd mcp
          uv run pytest -v

  build:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v6

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v4

      - name: Build Docker image
        uses: docker/build-push-action@v7
        with:
          context: ./mcp
          push: false
          tags: tee-sniper-mcp:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/mcp-build.yml
git commit -m "Add MCP build and test workflow"
```

### Task D3: Release workflow updates

**Files:**
- Modify: `.github/workflows/release.yml`
- Modify: `.github/workflows/build.yml`

- [ ] **Step 1: Add MCP image build/push to `release.yml`**

In `.github/workflows/release.yml`, after the `Build and push API Docker image` step, add:

```yaml
    - name: Extract metadata for MCP Docker image
      id: meta-mcp
      uses: docker/metadata-action@v6
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-mcp
        tags: |
          type=semver,pattern={{version}}
          type=semver,pattern={{major}}.{{minor}}
          type=raw,value=latest

    - name: Build and push MCP Docker image
      uses: docker/build-push-action@v7
      with:
        context: ./mcp
        push: true
        tags: ${{ steps.meta-mcp.outputs.tags }}
        labels: ${{ steps.meta-mcp.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
```

- [ ] **Step 2: Exclude `mcp/**` from the Go `build.yml`**

In `.github/workflows/build.yml`, update both `paths-ignore` lists (under `push` and `pull_request`) to add `'mcp/**'`:

```yaml
    paths-ignore:
      - 'api/**'
      - 'mcp/**'
      - 'k8s/**'
      - 'docs/**'
```

- [ ] **Step 3: Commit & open PR**

```bash
git add .github/workflows/release.yml .github/workflows/build.yml
git commit -m "Publish tee-sniper-mcp Docker image on release"
git push -u origin mcp/phaseD-docker-ci
gh pr create --title "Add MCP CI workflow and Docker release publishing" --body "Phase D of docs/superpowers/plans/2026-05-04-local-mcp-server.md. Adds mcp-build.yml (PR validation), publishes the tee-sniper-mcp image to GHCR on tag, and excludes mcp/** from the Go build workflow."
```

---

## Phase E — Documentation

**Branch:** `mcp/phaseE-docs`

### Task E1: `mcp/README.md`

**Files:**
- Modify: `mcp/README.md` (replace stub from Phase B)

- [ ] **Step 1: Replace the stub README**

Overwrite `mcp/README.md` with:

````markdown
# tee-sniper-mcp

Local stdio MCP server that exposes tee-sniper booking operations
(`find_tee_times`, `book_tee_time`, `list_partners`, `add_partners`) to LLM
clients. It is a thin client of the FastAPI service in `../api/`.

## Tools

| Tool | Purpose |
|---|---|
| `find_tee_times(date, [start_time], [end_time], [time_of_day])` | List available slots. `date` accepts ISO or relative (`tomorrow`, `next saturday`, `in 3 days`). Use `time_of_day` for fuzzy windows. |
| `book_tee_time(date, time, [num_slots], [dry_run])` | Book a slot. `num_slots` 1–4. |
| `list_partners()` | Configured playing partners (id → name). |
| `add_partners(booking_id, partner_ids, [dry_run])` | Add 1–3 partners to an existing booking. |

## Time-of-day bands

Defaults: `early_morning` 06–09, `morning` 09–12, `midday` 11–14,
`afternoon` 12–17, `early_evening` 17–19, `all_day` (no filter).

Override via `TSA_TIME_BANDS`, e.g.
`TSA_TIME_BANDS='{"morning":["07:00","11:00"]}'`.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `TSA_API_BASE_URL` | yes | URL of the running FastAPI service. |
| `TSA_USERNAME` | yes | Booking-site username. |
| `TSA_PIN` | yes | Booking-site PIN. |
| `TSA_SHARED_SECRET` | yes | Same value as the API's `TSA_SHARED_SECRET`. |
| `TSA_TIME_BANDS` | no | JSON object overriding the default bands. |

Login happens lazily on the first authenticated tool call, and the bearer
token is cached in memory for the lifetime of the MCP process. There is no
explicit `login` tool.

## Running

### From source via uv

```bash
cd mcp
uv sync
uv run tee-sniper-mcp
```

### Via Docker

```bash
docker run --rm -i \
  -e TSA_API_BASE_URL=http://host.docker.internal:8000 \
  -e TSA_USERNAME=... -e TSA_PIN=... -e TSA_SHARED_SECRET=... \
  ghcr.io/<owner>/tee-sniper-mcp:latest
```

## Claude Desktop config

```json
{
  "mcpServers": {
    "tee-sniper": {
      "command": "uv",
      "args": ["--directory", "/abs/path/to/tee-sniper/mcp", "run", "tee-sniper-mcp"],
      "env": {
        "TSA_API_BASE_URL": "http://localhost:8000",
        "TSA_USERNAME": "...",
        "TSA_PIN": "...",
        "TSA_SHARED_SECRET": "..."
      }
    }
  }
}
```

## MetaMCP config

```yaml
servers:
  tee-sniper:
    command: docker
    args:
      - run
      - --rm
      - -i
      - -e
      - TSA_API_BASE_URL
      - -e
      - TSA_USERNAME
      - -e
      - TSA_PIN
      - -e
      - TSA_SHARED_SECRET
      - ghcr.io/<owner>/tee-sniper-mcp:latest
    env:
      TSA_API_BASE_URL: http://api:8000
      TSA_USERNAME: ...
      TSA_PIN: ...
      TSA_SHARED_SECRET: ...
```

## Tests

```bash
cd mcp
uv run pytest -v
```
````

- [ ] **Step 2: Commit**

```bash
git add mcp/README.md
git commit -m "Flesh out mcp/README.md with usage and client config"
```

### Task E2: Top-level docs

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Delete: `docs/MCP_PLAN.md`

- [ ] **Step 1: Update top-level `README.md`**

Open `README.md` and add a new section "MCP server" (after the API section if one exists, otherwise after the Go CLI usage):

```markdown
## MCP server (local)

`mcp/` is a stdio MCP server that exposes tee-sniper booking operations to
LLM clients (Claude Desktop, MetaMCP, etc.) by calling the REST API.

```bash
cd mcp
uv sync
TSA_API_BASE_URL=http://localhost:8000 TSA_USERNAME=... TSA_PIN=... TSA_SHARED_SECRET=... \
  uv run tee-sniper-mcp
```

See `mcp/README.md` for tool reference, time-of-day bands, and Claude
Desktop / MetaMCP configuration snippets.
```

- [ ] **Step 2: Update `CLAUDE.md`**

Append a new section to `CLAUDE.md` (after the API workflow section):

```markdown
### MCP Server (Local)

**Location:** `mcp/` (Python project, managed with `uv`, run via `uv run tee-sniper-mcp`).

```bash
# Install + run tests
cd mcp && uv sync --all-extras --dev && uv run pytest

# Run the server
cd mcp && uv run tee-sniper-mcp
```

The MCP server is a stdio-only client of the REST API. It encrypts credentials
locally with the same AES-256-GCM scheme as `api/app/services/encryption.py`,
calls `/api/login` lazily, caches the bearer token in memory, and proxies four
tools (`find_tee_times`, `book_tee_time`, `list_partners`, `add_partners`) to
the existing endpoints. See `mcp/README.md` for the full tool reference.

## MCP Migration Workflow

When implementing the MCP plan (see `docs/superpowers/plans/2026-05-04-local-mcp-server.md`):

1. **Each phase must be completed in a separate PR.**
2. Per-phase: branch from `main`, implement tasks, run `cd mcp && uv run pytest`,
   commit, open PR, wait for review.
3. Phase order: A (API endpoint) → B (scaffold) → C (tools) → D (Docker+CI) → E (docs).
   B can run in parallel with A review; C depends on B; D depends on C; E depends on A+C.
```

- [ ] **Step 3: Delete the superseded plan**

Run: `git rm docs/MCP_PLAN.md`

- [ ] **Step 4: Commit & open PR**

```bash
git add README.md CLAUDE.md
git commit -m "Document MCP server in README and CLAUDE.md; remove superseded plan"
git push -u origin mcp/phaseE-docs
gh pr create --title "Document MCP server and remove superseded MCP_PLAN.md" --body "Phase E of docs/superpowers/plans/2026-05-04-local-mcp-server.md. Fleshes out mcp/README.md, adds an MCP section to the top-level README and CLAUDE.md, and deletes the superseded docs/MCP_PLAN.md."
```

---

## Self-review checklist

Before declaring the plan complete, verify these against the spec
(`docs/superpowers/specs/2026-05-03-local-mcp-server-design.md`):

- Architecture (stdio MCP via uv → REST API): tasks B1, C2.
- Layout under `mcp/src/tee_sniper_mcp/`: tasks B1, B2, B3, B4, B5, C1, C2.
- Required env vars + missing-var error: tasks B2, C2.
- AES-GCM encryption matching `api/`: task B4 (with cross-package roundtrip test).
- Lazy login + 401 retry: tasks B4 (login), B5 (retry).
- Four tools with the documented signatures and return shapes: task C1.
- Time-of-day bands incl. `TSA_TIME_BANDS` override: tasks B3, C1.
- Date parsing covers ISO + `today`/`tomorrow`/`next <weekday>`/`this <weekday>`/`in N days`: task B3.
- `GET /api/partners` endpoint backed by `TSA_PARTNERS_FILE`: tasks A1–A4.
- Docker image: task D1.
- `mcp-build.yml` PR workflow: task D2.
- `release.yml` publishes `<repo>-mcp` image: task D3.
- `build.yml` excludes `mcp/**`: task D3.
- README + CLAUDE.md + delete `docs/MCP_PLAN.md`: tasks E1, E2.
