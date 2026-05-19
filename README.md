# Tee-Sniper

Automated golf tee-time booking. A Python FastAPI service stores encrypted
credentials and booking sessions in Redis; the **wanted** API registers
persisted booking requests (one-shot by date, or recurring by day-of-week);
a daily worker processes due requests, books a matching slot, records the
outcome, and optionally sends a Twilio SMS. An optional local MCP server
exposes the booking operations to Claude Desktop / MetaMCP.

## Components

| Component | Path | Purpose |
|-----------|------|---------|
| API service | `api/` | FastAPI: login, find/book tee times, manage partners, `wanted` requests |
| Worker | `api/app/cli/worker.py` | Processes due `wanted` requests (run as a CronJob) |
| MCP server | `mcp/` | Local stdio MCP client of the REST API |
| Helm chart | `charts/tee-sniper-api/` | Deploys API + Redis + opt-in worker CronJob |

## How It Works

1. A client logs in via `POST /api/login`; credentials are encrypted
   (AES-256-GCM) and a session is stored in Redis with a sliding TTL.
2. Tee times are searched and booked through the booking endpoints.
3. For unattended booking, register a **wanted** request:
   - `POST /api/wanted?kind=one_shot|recurring` — create a request
   - `GET /api/wanted[?status=pending|booked|expired|disabled]` — list
   - `GET /api/wanted/{slot_id}` — fetch one (incl. attempt history)
   - `PATCH /api/wanted/{slot_id}` — update window/partners/notify or disable
   - `DELETE /api/wanted/{slot_id}` — remove
4. The worker (`python -m app.cli.worker`, deployed as the opt-in `worker`
   Helm CronJob) runs daily, books due requests, records the outcome, and
   optionally sends a Twilio SMS. This worker + the `wanted` API replace
   the retired Go CLI and its external cron.

All endpoints except `/health` and `/api/login` require an
`Authorization: Bearer <token>` header obtained from the login endpoint.

## Configuration

The API is configured via environment variables prefixed `TSA_`
(see `api/app/config.py` and `.env.example`):

| Variable | Description | Required |
|----------|-------------|----------|
| `TSA_SHARED_SECRET` | Credential encryption secret | Yes |
| `TSA_BASE_URL` | Booking site base URL | Yes |
| `TSA_REDIS_URL` | Redis connection URL | Yes (prod) |
| `TSA_TWILIO_ACCOUNT_SID` | Twilio SID (SMS notifications) | No |
| `TSA_TWILIO_AUTH_TOKEN` | Twilio auth token | No |
| `TSA_TWILIO_FROM_NUMBER` | Twilio sender number | No |
| `TSA_LOG_LEVEL` | `DEBUG`/`INFO`/`WARNING`/`ERROR` | No (`INFO`) |
| `TSA_LOG_FORMAT` | `json` or `text` | No (`json`) |
| `TSA_REQUIRE_REDIS` | Test-only; `1` makes session integration tests fail loudly instead of skipping when Redis is down (set in CI) | No |

## Running Locally

```bash
# API + Redis via Docker Compose (dev override auto-loaded)
docker compose up

# Or run the API directly
cd api && .venv/bin/python -m uvicorn app.main:app --reload

# Run the wanted-slot worker once
cd api && .venv/bin/python -m app.cli.worker
```

## Deployment

Deploy with the Helm chart in `charts/tee-sniper-api/` (API + Redis, with
an opt-in `worker` CronJob for `wanted` processing):

```bash
helm template charts/tee-sniper-api          # render
# install/upgrade per your environment values file
```

See `charts/tee-sniper-api/values*.yaml` for environment-specific values.

## MCP Server

A local stdio MCP server proxies the booking API to Claude Desktop /
MetaMCP. See `mcp/README.md` for install, configuration, and the tool
reference.

## Development & Testing

```bash
# Python API tests
cd api && .venv/bin/python -m pytest tests/ -v

# MCP tests
cd mcp && uv sync --all-extras --dev && uv run pytest

# Session integration tests need a real Redis (skip silently without one):
docker run -d -p 6379:6379 redis
cd api && .venv/bin/python -m pytest tests/test_session_integration.py
```

## CI/CD

- `.github/workflows/api-build.yml` — API build/test (provisions Redis,
  sets `TSA_REQUIRE_REDIS=1`).
- `.github/workflows/mcp-build.yml` — MCP build/test.
- `.github/workflows/helm-chart.yml` — Helm chart lint/package.
- `.github/workflows/release.yml` — on `v*.*.*` tags: builds and pushes
  the API Docker image (`ghcr.io/<repo>-api`), the MCP Docker image
  (`ghcr.io/<repo>-mcp`), and the MCP wheel + sdist as release assets.

## Roadmap

Planned follow-up work (see `docs/superpowers/specs/` for designs):

- [ ] **MCP tools for wanted tee-times** — expose create/list/delete of
  wanted-slots via the MCP server (separate spec to follow).

## License

See `LICENSE`.
