# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Running the Application
```bash
# Run with command line arguments
go run cmd/tee-sniper/main.go -h

# Run using the convenience script (sources .env file)
./run-teesniper.sh

# Example with all parameters
go run cmd/tee-sniper/main.go -u username -p pin -b https://example.com/ -d 7 -t 15:00 -e 17:00 -n toNumber -f fromNumber -s "partner1,partner2"
```

### Testing
```bash
# Run Go tests
go test ./...

# Run Go tests for specific package
go test ./pkg/teetimes/

# Run Python API tests
cd api && .venv/bin/python -m pytest tests/ -v

# Run specific Python test file
cd api && .venv/bin/python -m pytest tests/test_booking_routes.py -v
```

### Building
```bash
# Build the application
go build -o tee-sniper cmd/tee-sniper/main.go
```

## Code Architecture

### Project Structure

**Go CLI:**
- `cmd/tee-sniper/main.go` - Main application entry point
- `pkg/config/` - Configuration handling using go-flags
- `pkg/models/` - Data models (TimeSlot, etc.)
- `pkg/clients/` - External service clients (Twilio, booking site)
- `pkg/teetimes/` - Core business logic for filtering and selecting tee times

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

### Core Components

**Main Application Flow** (cmd/tee-sniper/main.go):
1. Parses command line configuration
2. Creates booking and Twilio clients
3. Logs into booking site
4. Searches for available tee times within specified date/time range
5. Filters, sorts, and randomly selects from available slots
6. Books the selected time slot with retry logic
7. Sends SMS confirmation via Twilio

**Configuration** (pkg/config/config.go):
Uses jessevdk/go-flags for command line argument parsing. All required parameters must be provided via CLI flags or the application will exit with help text. The optional `-s/--partners` flag accepts a comma-separated list of playing partner IDs to book additional slots.

**Tee Time Logic** (pkg/teetimes/teetimes.go):
- `FilterByBookable()` - Filters to only bookable slots
- `SortTimesAscending()` - Sorts times chronologically
- `FilterBetweenTimes()` - Filters by time range
- `PickRandomTime()` - Randomly selects from available options

**External Dependencies**:
- Twilio Go SDK for SMS notifications
- PuerkitoBio/goquery for HTML parsing/scraping
- jessevdk/go-flags for CLI argument parsing

### Environment Variables
The application expects Twilio credentials as environment variables:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`

### GitHub Actions Integration
The repository includes CI workflows in `.github/workflows/`:
- `build.yml` - Runs build and tests on push/PR to main
- `release.yml` - Handles release automation

## Testing Workflow

When implementing the comprehensive testing plan (see `TESTING_PLAN.md`):

1. **Each phase must be completed in a separate PR**
2. Follow this workflow per phase:
   - Create feature branch from `main` (e.g., `test/phase1-interfaces-mocks`)
   - Implement tests for that phase only
   - Run `go test ./...` to verify all tests pass
   - Commit changes with descriptive message
   - Push branch and create PR
   - Merge PR to `main` before starting next phase
3. Respect phase dependencies - Phase 1 (interfaces/mocks) must be merged before phases that require mocking

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

## Docker Migration Workflow

When implementing the Docker migration plan (see `docs/DOCKER_PLAN.md`):

1. **Each phase must be completed in a separate PR**
2. Follow this workflow per phase:
   - Create feature branch from `main` (e.g., `docker/phase2-config-refactor`)
   - Implement the phase tasks
   - Run `go test ./...` to verify all tests pass
   - Test Docker builds locally where applicable
   - Update `docs/DOCKER_PLAN.md` to mark completed tasks
   - Update `README.md` with any new usage instructions
   - Commit changes with descriptive message
   - Push branch and create PR for review
   - Wait for PR to be reviewed and merged before starting next phase
3. Phase dependencies:
   - Phase 1 (Docker) must be complete before Phase 3 (CI/CD)
   - Phase 2 (Config refactor) can run in parallel with Phase 3

### MCP Server (Local)

**Location:** `mcp/` (Python 3.14 project, managed with `uv`, runnable via `uv run tee-sniper-mcp` or the `ghcr.io/<repo>-mcp` Docker image).

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