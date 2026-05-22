# Tee-Sniper

Automated golf tee-time booking. A Python FastAPI service stores encrypted
credentials and booking sessions in Redis; the **wanted** API registers
persisted booking requests (one-shot by date, or recurring by day-of-week);
a daily worker processes due requests, books a matching slot, records the
outcome, and optionally sends a Twilio SMS. A React web UI drives the wanted
workflow in the browser, and an optional local MCP server exposes the booking
operations to Claude Desktop / MetaMCP.

## Components

| Component | Path | Purpose |
|-----------|------|---------|
| API service | `api/` | FastAPI: login, find/book tee times, manage partners, `wanted` requests |
| Worker | `api/app/cli/worker.py` | Processes due `wanted` requests (run as a CronJob) |
| Web UI | `web/` | Vite + React SPA for the wanted tee-times workflow (nginx-served) |
| MCP server | `mcp/` | Local stdio MCP client of the REST API |
| API Helm chart | `charts/tee-sniper-api/` | Deploys API + Redis + opt-in worker CronJob |
| Web Helm chart | `charts/tee-sniper-web/` | Deploys the web UI with path-based ingress (`/api/*` → API, `/*` → web) |

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
# API + web + Redis via Docker Compose (dev override auto-loaded).
# API on :8000, web UI on :8080, Redis on :6379.
docker compose up

# Or run the API directly
cd api && .venv/bin/python -m uvicorn app.main:app --reload

# Run the web UI dev server (proxies /api → http://localhost:8000)
cd web && npm install && npm run dev      # serves on :5173

# Run the wanted-slot worker once
cd api && .venv/bin/python -m app.cli.worker
```

The web UI reads its API base URL from `window.__TSA_CONFIG__.apiBaseUrl`,
rewritten from the `API_BASE_URL` env var at container start (empty → relative
`/api/*`). See `web/README.md` for details.

## Deployment

Two Helm charts deploy the stack. Both pin images by tag (the API chart's
schema rejects `tag=latest`); set `image.tag` / `api.image.tag` to a released
version.

### API chart (`charts/tee-sniper-api/`)

Deploys the API, a bundled Redis (Bitnami subchart), and an opt-in `worker`
CronJob for `wanted` processing. Requires `helm dep update` first to pull the
Redis dependency.

```bash
helm dep update charts/tee-sniper-api
helm template testrel charts/tee-sniper-api -f charts/tee-sniper-api/values-dev.yaml   # render
helm upgrade --install tee-sniper-api charts/tee-sniper-api \
  -f charts/tee-sniper-api/values-prod.yaml
```

Key values (see `charts/tee-sniper-api/values.yaml`, `values-dev.yaml`,
`values-prod.yaml`):

| Value | Default | Purpose |
|-------|---------|---------|
| `api.image.tag` | `.Chart.AppVersion` | API image tag (required, not `latest`) |
| `api.existingSecret` | `tee-sniper-api` | Secret with `TSA_*` env (shared secret, base URL, etc.) |
| `worker.enabled` | `false` | Enable the daily `wanted` worker CronJob |
| `worker.schedule` | `30 6 * * *` | Worker cron schedule |
| `worker.twilio.enabled` | `false` | Mount Twilio creds for SMS notifications |
| `redis.enabled` | `true` | Deploy the bundled Redis subchart |
| `networkPolicy.enabled` | `false` | Restrict API ingress to labelled clients |

When `worker.enabled=true` you must also have `redis.enabled=true` or supply
`TSA_REDIS_URL` via the chart secret — otherwise the worker connects to
localhost and fails.

### Web chart (`charts/tee-sniper-web/`)

Deploys the nginx-served React UI with a path-based ingress that routes
`/api/*` to the API service and `/*` to the web service on the same host.

```bash
helm template testrel charts/tee-sniper-web      # render
helm upgrade --install tee-sniper-web charts/tee-sniper-web \
  --set ingress.host=tee-sniper.example.com
```

Key values (see `charts/tee-sniper-web/values.yaml`):

| Value | Default | Purpose |
|-------|---------|---------|
| `image.tag` | `.Chart.AppVersion` | Web image tag |
| `apiBaseUrl` | `""` | Browser API base; empty → relative `/api/*` (same-host ingress) |
| `ingress.enabled` | `true` | Create the path-split ingress |
| `ingress.host` | `tee-sniper.example.com` | Ingress hostname |
| `ingress.apiServiceName` | `tee-sniper-api` | Service to route `/api/*` to |
| `ingress.tls.enabled` | `false` | Enable TLS (set `ingress.tls.secretName`) |

## MCP Server

A local stdio MCP server proxies the booking API to Claude Desktop /
MetaMCP. See `mcp/README.md` for install, configuration, and the tool
reference.

## Development & Testing

```bash
# Python API tests
cd api && .venv/bin/python -m pytest tests/ -v

# Web tests (Vitest + RTL + MSW)
cd web && npm install && npm test && npm run lint && npm run build

# MCP tests
cd mcp && uv sync --all-extras --dev && uv run pytest

# Session integration tests need a real Redis (skip silently without one):
docker run -d -p 6379:6379 redis
cd api && .venv/bin/python -m pytest tests/test_session_integration.py
```

## CI/CD

- `.github/workflows/api-build.yml` — API build/test (provisions Redis,
  sets `TSA_REQUIRE_REDIS=1`).
- `.github/workflows/web-build.yml` — Web lint/test/build, then a Docker
  image build on PRs/pushes (built only, not pushed).
- `.github/workflows/mcp-build.yml` — MCP build/test.
- `.github/workflows/helm-chart.yml` — Helm chart lint + `kubeconform`
  validation of the API chart's dev/prod values (and asserts the schema
  rejects `tag=latest`).
- `.github/workflows/release.yml` — on `v*.*.*` tags: builds and pushes
  the API Docker image (`ghcr.io/<repo>-api`), the web Docker image
  (`ghcr.io/<repo>-web`), the MCP Docker image (`ghcr.io/<repo>-mcp`), and
  the MCP wheel + sdist as release assets.

## License

See `LICENSE`.
