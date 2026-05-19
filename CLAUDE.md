# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Running the Application
```bash
# Run the API (FastAPI)
cd api && .venv/bin/python -m uvicorn app.main:app --reload

# Or the full stack via Docker Compose
docker compose up

# Run the wanted-slot worker once
cd api && .venv/bin/python -m app.cli.worker
```

### Testing
```bash
# Run Python API tests
cd api && .venv/bin/python -m pytest tests/ -v

# Run specific Python test file
cd api && .venv/bin/python -m pytest tests/test_booking_routes.py -v

# Run the wanted-slot worker once (needs TSA_* env, see api/app/config.py)
cd api && .venv/bin/python -m app.cli.worker

# Session integration tests need a real Redis. Without one they SKIP:
docker run -d -p 6379:6379 redis   # then: cd api && .venv/bin/python -m pytest tests/test_session_integration.py
```

**`TSA_REQUIRE_REDIS`**: the session integration tests
(`tests/test_session_integration.py`) skip silently when Redis is
unreachable — convenient locally, dangerous in CI (a broken Redis service
would yield a green build that stopped regression-testing session handling).
Setting `TSA_REQUIRE_REDIS=1` turns that silent skip into a hard collection
error. It is set in `.github/workflows/api-build.yml` (which also provisions
a `redis:8-alpine` service), so CI always runs these tests and fails loudly
if Redis is missing. Leave it unset locally to keep the skip-when-absent
convenience.

## Code Architecture

### Project Structure

**Python API** (`api/`):
- `api/app/main.py` - FastAPI application entry point with health endpoint
- `api/app/config.py` - Settings via pydantic-settings (TSA_ env prefix)
- `api/app/dependencies.py` - DI providers (Redis, session, auth, booking client)
- `api/app/routers/booking.py` - All API endpoints (login, times, book, partners)
- `api/app/services/booking_client.py` - Async HTTP client for booking site
- `api/app/services/session_manager.py` - Redis session management with sliding TTL
- `api/app/services/encryption.py` - AES-256-GCM credential encryption
- `api/app/models/` - Pydantic request/response/domain models
- `api/app/utils/` - HTML parser, user agent rotation

### Environment Variables
All configuration is `TSA_`-prefixed and read by `api/app/config.py`
(pydantic-settings). See `.env.example` for the common variables and
`api/app/config.py` for the full set, including optional
`TSA_TWILIO_ACCOUNT_SID` / `TSA_TWILIO_AUTH_TOKEN` /
`TSA_TWILIO_FROM_NUMBER` for SMS notifications.

### GitHub Actions Integration
The repository includes CI workflows in `.github/workflows/`:
- `api-build.yml` - API build/test (provisions Redis, sets `TSA_REQUIRE_REDIS=1`)
- `mcp-build.yml` - MCP build/test
- `helm-chart.yml` - Helm chart lint/package
- `release.yml` - on `v*.*.*` tags, builds and pushes the API image
  (`ghcr.io/<repo>-api`), the MCP image (`ghcr.io/<repo>-mcp`), and the
  MCP wheel + sdist as release assets

## API Migration Workflow

When implementing the API migration plan (see `docs/API_MIGRATION_PLAN.md`):

1. **Each phase must be completed in a separate PR**
2. Follow this workflow per phase:
   - Create feature branch from `main` (e.g., `api/phase4-endpoints`)
   - Implement the phase tasks
   - Run `cd api && .venv/bin/python -m pytest tests/ -v` to verify all tests pass
   - Update `docs/API_MIGRATION_PLAN.md` to mark completed tasks
   - Commit changes with descriptive message
   - Push branch and create PR for review
   - Wait for PR to be reviewed and merged before starting next phase
3. Completed phases: 1 (Foundation), 2 (Redis), 3 (Booking Client), 4 (API Endpoints)

## Wanted Tee-Times

Persisted auto-booking requests. Spec:
`docs/superpowers/specs/2026-05-16-wanted-tee-times-design.md`.
Plan: `docs/superpowers/plans/2026-05-16-wanted-tee-times.md`.

- Models: `api/app/models/wanted.py`
- Store: `api/app/services/wanted_store.py` (Redis `wanted:{id}` + `wanted:index`)
- Scheduling predicate: `api/app/services/scheduling.py` (`is_due`, 8-day window)
- Worker: `api/app/services/worker.py` (`run_once`), CLI `api/app/cli/worker.py`
- Router: `api/app/routers/wanted.py` (`/api/wanted`)
- Deploy: opt-in `worker` CronJob in `charts/tee-sniper-api`

### MCP Server (Local)

**Location:** `mcp/` (Python 3.14 project, managed with `uv`, runnable via `uv run tee-sniper-mcp`, the `ghcr.io/<repo>-mcp` Docker image, or the `tee_sniper_mcp-<version>-py3-none-any.whl` attached to each `v*.*.*` GitHub Release — see `mcp/README.md` for install commands). Version is derived from the git tag via `hatch-vcs`.

```bash
# Install + run mcp tests
cd mcp && uv sync --all-extras --dev && uv run pytest

# Run the stdio server (requires TSA_API_BASE_URL, TSA_USERNAME, TSA_PIN, TSA_SHARED_SECRET)
cd mcp && uv run tee-sniper-mcp
```

The MCP server is a stdio-only client of the REST API. It encrypts credentials
locally with the same AES-256-GCM scheme as `api/app/services/encryption.py`,
calls `/api/login` lazily, caches the bearer token in memory, and proxies four
tools (`find_tee_times`, `book_tee_time`, `list_partners`, `add_partners`) to
the existing endpoints. See `mcp/README.md` for the full tool reference,
configuration env vars, time-of-day bands, and Claude Desktop / MetaMCP config
snippets.

**Key design choices (rationale in `docs/superpowers/specs/2026-05-03-local-mcp-server-design.md`):**

- **Local stdio, not a mounted HTTP endpoint.** Simpler to deploy, no public auth
  surface, plays directly with Claude Desktop / MetaMCP via `uv run` or Docker.
- **In-memory token cache only.** MetaMCP keeps the server long-lived (it spawns
  the child process once per session and proxies tool calls to it), so a single
  booking flow = one login. No disk persistence — simplifies the failure modes.
- **Inline AES-GCM, not a shared package.** `mcp/src/tee_sniper_mcp/auth.py`
  re-implements the encryption (~20 lines) instead of importing
  `app.services.encryption`. The cross-package roundtrip test in
  `mcp/tests/test_auth.py` guards against drift.
- **Partners come from `TSA_PARTNERS_FILE`** (JSON `{id: name}`), not from
  scraping the booking site. Endpoint: `GET /api/partners` (auth-required).

**Operational notes:**

- `mcp/conftest.py` puts `api/` on `sys.path` for the encryption-roundtrip test.
  This causes `app/services/__init__.py` to load, which re-exports from
  `session_manager.py` (uses `redis`). That is why `redis` is in
  `mcp/pyproject.toml`'s `dev` dep group — it is **not** scope creep; removing
  it breaks the test. Comment in the file explains.
- FastMCP ≥ 3.2 exposes registered tools via `await mcp.list_tools()` (older
  `get_tools()` is gone). The smoke test in `mcp/tests/test_tools.py` uses
  `list_tools`.
- Configuration errors at startup print
  `tee-sniper-mcp: configuration error: …` to stderr and exit with code 2.
- The Dockerfile uses `pip install .` (not `uv sync --frozen`), so Docker
  builds resolve transitive deps from PyPI at build time. If reproducibility
  becomes important, switch to a uv-based install in `mcp/Dockerfile`.

### MCP Plan History

- Spec: `docs/superpowers/specs/2026-05-03-local-mcp-server-design.md`
- Plan: `docs/superpowers/plans/2026-05-04-local-mcp-server.md`
- Shipped via PR #71 (single PR covering all 5 phases — A: API endpoint,
  B: scaffold, C: tools, D: Docker+CI, E: docs).