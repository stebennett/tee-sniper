# Local MCP Server Design

**Status:** Draft
**Date:** 2026-05-03
**Supersedes:** `docs/MCP_PLAN.md` (remote/mounted MCP design — to be deleted on merge)
**Related issue:** #66

## Goal

Provide an MCP server that lets an LLM-driven client (Claude Desktop, MetaMCP, etc.)
find, book, and add partners to tee times by calling the existing `api/` REST service.

The server runs **locally as a stdio MCP process**, launched via `uv`. It is a thin
client of the REST API — no booking-site coupling, no Redis, no shared Python
package with `api/`.

## Non-goals

- Hosting a remote/HTTP-mounted MCP endpoint (the previous `docs/MCP_PLAN.md`
  approach). The local model is simpler to deploy, safer (no public auth surface),
  and works directly with MetaMCP and Claude Desktop.
- Discovering partners by scraping the booking site. Partners come from a
  config file on the API side.
- Persisting auth tokens to disk. In-memory cache is sufficient given MetaMCP
  keeps the server long-lived.

## Architecture

```
┌──────────────┐  stdio MCP  ┌────────────────┐  HTTP   ┌─────────────┐
│  MCP client  │ ──────────► │  mcp/ (uv run) │ ──────► │  FastAPI    │
│  (Claude /   │             │  - tools       │         │  api/*      │
│   MetaMCP)   │             │  - auth state  │         └─────────────┘
└──────────────┘             │  - date parser │
                             └────────────────┘
```

A new top-level `mcp/` directory is added alongside `api/`. It is a standalone
Python project with its own `pyproject.toml`, runnable via `uv run tee-sniper-mcp`
(or `uvx tee-sniper-mcp` once published).

### Layout

```
mcp/
  pyproject.toml            # uv-managed deps: fastmcp, httpx, python-dateutil
  README.md                 # quick-start + sample claude_desktop_config.json
  src/tee_sniper_mcp/
    __init__.py
    server.py               # FastMCP server, tool registration, entrypoint
    config.py               # env-var loading
    api_client.py           # async httpx wrapper around the REST API
    auth.py                 # encrypts credentials, manages token lifecycle
    dates.py                # date / time / band parsing
    tools.py                # the 4 MCP tool implementations
  tests/
    test_auth.py
    test_dates.py
    test_tools.py           # uses respx to mock the REST API
  Dockerfile                # publishes the MCP server as a runnable image
```

## Configuration

All configuration is via environment variables, matching MCP-server convention
(env is the natural way clients pass config in `claude_desktop_config.json` /
MetaMCP config blocks).

| Variable | Required | Description |
|---|---|---|
| `TSA_API_BASE_URL` | yes | Base URL of the running FastAPI service (e.g. `http://localhost:8000`). |
| `TSA_USERNAME` | yes | Booking-site username. |
| `TSA_PIN` | yes | Booking-site PIN. |
| `TSA_SHARED_SECRET` | yes | Same secret as `api/`'s `TSA_SHARED_SECRET`; used to encrypt credentials before calling `/api/login`. |
| `TSA_TIME_BANDS` | no | JSON override for the named time-of-day bands. See **Date & time parsing**. |

Missing required vars → tools return `{"error": "TSA_USERNAME not configured", ...}`
on first invocation. The process does not crash on import.

## Auth & token lifecycle

In-process `AuthManager` (in `auth.py`):

- Holds `access_token` + `expires_at` in memory.
- `get_token()` returns the cached token if valid, otherwise calls `_login()`.
- `_login()`:
  1. Reads `TSA_USERNAME` / `TSA_PIN` / `TSA_SHARED_SECRET` from env.
  2. Encrypts `username:pin` using AES-256-GCM with the shared secret. The
     encryption is re-implemented inline (~20 lines) — same algorithm as
     `api/app/services/encryption.py` but no shared package between `mcp/`
     and `api/`.
  3. POSTs `/api/login`, stores token + `expires_at`.
- All tool calls go through `api_client.request()`, which:
  1. Calls `get_token()` and sets `Authorization: Bearer <token>`.
  2. On `401`, clears the cached token and retries **once**.
- No persistence to disk. MetaMCP keeps the server long-lived, so the in-memory
  cache survives the lifetime of the MCP session — typically one login per booking
  flow.

## MCP tool surface

Four tools. All take/return JSON-friendly types. Errors are returned as
`{"error": "...", "details": {...}}` dicts (not raised exceptions) so the LLM
can act on them.

### `find_tee_times`

Find available tee times on a given date.

| Arg | Type | Notes |
|---|---|---|
| `date` | str | ISO `YYYY-MM-DD`, `today`, `tomorrow`, `next saturday`, `this friday`, `in 3 days`. |
| `start_time` | str? | `HH:MM` or `3pm` / `3:30 PM`. Optional. |
| `end_time` | str? | Same formats as `start_time`. Optional. |
| `time_of_day` | str? | One of: `early_morning`, `morning`, `midday`, `afternoon`, `early_evening`, `all_day`. Ignored if `start_time` or `end_time` is provided. |

Returns: `{"date": "YYYY-MM-DD", "slots": [{"time": "HH:MM", "num_available": int}, ...]}`.

Calls `GET /api/{date}/times?start=...&end=...`.

### `book_tee_time`

Book a tee time.

| Arg | Type | Notes |
|---|---|---|
| `date` | str | Same date formats as above. |
| `time` | str | `HH:MM` or `3pm`. |
| `num_slots` | int | 1–4, default 1. |
| `dry_run` | bool | Default false. |

Returns: `{"booking_id": str, "date": str, "time": str, "num_slots": int, "dry_run": bool}`.

Calls `POST /api/{date}/time/{time}/book`.

### `list_partners`

List configured playing partners.

No args.

Returns: `{"partners": [{"id": str, "name": str}, ...]}`.

Calls **new endpoint** `GET /api/partners` (see **REST API gaps** below).

### `add_partners`

Add 1–3 playing partners to an existing booking.

| Arg | Type | Notes |
|---|---|---|
| `booking_id` | str | From a previous `book_tee_time` response. |
| `partner_ids` | list[str] | 1–3 IDs from `list_partners`. |
| `dry_run` | bool | Default false. |

Returns: `{"booking_id": str, "partners_added": [str], "partners_failed": [str]}`.

Calls `PATCH /api/bookings/{booking_id}`.

## Date & time parsing (`dates.py`)

- `parse_date(s) -> datetime.date`. Tries `datetime.date.fromisoformat` first;
  falls back to a small handler for `today` / `tomorrow` / `in N days` /
  `this <weekday>` / `next <weekday>`; finally `dateutil.parser.parse` with
  future-preferred settings. On failure, the calling tool returns
  `{"error": "could not parse date '<s>'"}`.
- `parse_time(s) -> "HH:MM"`. Accepts `"15:00"`, `"3pm"`, `"3:30 PM"`.
- `resolve_band(name) -> (start, end)` using the table below. Overridable via
  `TSA_TIME_BANDS` env var (JSON: `{"early_morning": ["06:00", "09:00"], ...}`).

| Band | Default range |
|---|---|
| `early_morning` | 06:00–09:00 |
| `morning` | 09:00–12:00 |
| `midday` | 11:00–14:00 |
| `afternoon` | 12:00–17:00 |
| `early_evening` | 17:00–19:00 |
| `all_day` | (no filter) |

`find_tee_times` resolves the time window in this order:

1. Explicit `start_time` / `end_time` (either or both) — wins.
2. Else `time_of_day` band.
3. Else no filter.

## REST API gaps

One new endpoint is required. It is small enough to ship in its own PR before
the MCP work begins (Phase A in the implementation plan).

### `GET /api/partners` (new)

- Auth: requires Bearer token (consistent with other authed endpoints).
- Reads partners from a config file path: new setting `TSA_PARTNERS_FILE` in
  `api/app/config.py`.
- File format: JSON, `{ "id1": "Alice Smith", "id2": "Bob Jones" }`.
- Response: `{"partners": [{"id": "id1", "name": "Alice Smith"}, ...]}`.
- If `TSA_PARTNERS_FILE` is unset or the file is missing, return `{"partners": []}`
  and log a warning. Do not 500.
- Tests: missing file, malformed JSON, valid file, auth required.

No other API changes are needed. `login`, `times`, `book`, and `add_partners`
endpoints all already exist.

## Testing

- `tests/test_dates.py` — table-driven parser tests: date phrases, time formats,
  band resolution including `TSA_TIME_BANDS` override.
- `tests/test_auth.py` — encryption produces a blob the API can decrypt (use
  the same algorithm + a known secret to assert round-trip); lazy login;
  401 refresh; missing-env error path. HTTP mocked with `respx`.
- `tests/test_tools.py` — each tool: happy path, error mapping, dry-run
  pass-through. HTTP mocked with `respx`.
- No live-API integration tests in CI (matches existing `api/` test style).

## CI / CD

Mirrors the existing per-component pattern (`build.yml` for Go, `api-build.yml`
for the Python API, `release.yml` for tagged Docker publishes).

### `.github/workflows/mcp-build.yml` (new)

Runs on pushes / PRs that touch `mcp/**` or the workflow itself.

- `actions/setup-python@v6` (3.14, matching `api-build.yml`).
- Install `uv` (`astral-sh/setup-uv` action).
- `cd mcp && uv sync --all-extras --dev`.
- `uv run pytest` (with coverage).
- Build Docker image (no push) to verify the `mcp/Dockerfile` is healthy on
  every PR — same shape as the `build` job in `api-build.yml`.

### `mcp/Dockerfile` (new)

Slim Python image (`python:3.14-slim`), `uv pip install` the project, default
`CMD` is `tee-sniper-mcp` so MetaMCP / Docker-based MCP clients can run it as
`docker run -i --rm -e TSA_USERNAME=... ghcr.io/<repo>-mcp tee-sniper-mcp`.

### Updates to `release.yml`

Add a third image build/push step (matching the existing Go and API blocks):

- Image name: `${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-mcp`.
- Context: `./mcp`.
- Same semver tagging (`{{version}}`, `{{major}}.{{minor}}`, `latest`).
- Same dual-registry login (GHCR + `dhi.io`) already configured in the workflow.

### Updates to `build.yml`

Add `mcp/**` to the existing `paths-ignore` list so Go pushes don't re-run for
MCP-only changes (mirrors the existing `api/**` exclusion).

### Release artefacts

Each tagged release will publish three Docker images to GHCR:

| Image | Purpose |
|---|---|
| `<repo>` | Go CLI (existing). |
| `<repo>-api` | FastAPI service (existing). |
| `<repo>-mcp` | New: MCP server, runnable via `docker run` or pulled by MetaMCP. |

Publishing to PyPI / `uvx`-from-PyPI is **out of scope** for this spec — local
users run via `uv run` against the source checkout, MetaMCP / containerised
users run via the Docker image. PyPI can be added later without affecting any
of the design above.

## Implementation phases

Each phase is its own PR. Per `CLAUDE.md` workflow conventions.

| Phase | Branch | Scope |
|---|---|---|
| **A** — partners endpoint | `mcp/phaseA-partners-endpoint` | `GET /api/partners`, `TSA_PARTNERS_FILE` config, tests. No `mcp/` changes. |
| **B** — MCP scaffold | `mcp/phaseB-scaffold` | `mcp/pyproject.toml`, `config.py`, `auth.py`, `api_client.py`, `dates.py` + their tests. No tools wired yet. |
| **C** — tools | `mcp/phaseC-tools` | `tools.py` + `server.py` entrypoint; `tests/test_tools.py`. Server is end-to-end runnable via `uv run`. |
| **D** — Docker + CI | `mcp/phaseD-docker-ci` | `mcp/Dockerfile`, new `.github/workflows/mcp-build.yml`, update `release.yml` to publish `<repo>-mcp` image, update `build.yml` `paths-ignore`. |
| **E** — docs | `mcp/phaseE-docs` | `mcp/README.md` with `uv run` + Docker + sample `claude_desktop_config.json` + MetaMCP snippets; update top-level `README.md` + `CLAUDE.md`; **delete `docs/MCP_PLAN.md`** (superseded). |

Phase B can begin in parallel with Phase A review. Phase C depends on B.
Phase D depends on C (needs a buildable project to image). Phase E depends
on A + C.
