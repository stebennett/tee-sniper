# tee-sniper-mcp

Local stdio MCP server that exposes tee-sniper booking operations
(`find_tee_times`, `book_tee_time`, `list_partners`, `add_partners`) to LLM
clients (Claude Desktop, MetaMCP, etc.). It is a thin HTTP client of the
FastAPI service in `../api/`.

## Architecture

```
┌──────────────┐  stdio MCP  ┌────────────────┐  HTTP   ┌─────────────┐
│  MCP client  │ ──────────► │  mcp/ (uv run) │ ──────► │  FastAPI    │
│  (Claude /   │             │  - tools       │         │  api/*      │
│   MetaMCP)   │             │  - auth state  │         └─────────────┘
└──────────────┘             │  - date parser │
                             └────────────────┘
```

The server logs in lazily on the first authenticated tool call, caches the
bearer token in memory for the lifetime of the process, and refreshes once on
401. MetaMCP keeps the child process alive across tool calls within a session,
so a typical booking flow performs exactly one login.

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

### Install from a GitHub Release

Each `v*.*.*` tag publishes `tee_sniper_mcp-<version>-py3-none-any.whl` and a
matching sdist as Release assets. Because this repo is private, you need a
GitHub PAT with `Contents: Read` on the repo (classic PAT: `repo` scope; fine-
grained: `Contents` read-only) to download them.

```bash
export GH_TOKEN=ghp_...
VERSION=0.1.0
WHEEL_URL="https://${GH_TOKEN}@github.com/<owner>/tee-sniper/releases/download/v${VERSION}/tee_sniper_mcp-${VERSION}-py3-none-any.whl"

# persistent install
uv tool install "${WHEEL_URL}"
tee-sniper-mcp --version

# or, one-shot via uvx (no install)
uvx --from "${WHEEL_URL}" tee-sniper-mcp --version
```

`uv tool install` and `uvx` both require Python 3.14 available; uv will fetch
it automatically.

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

### Via Docker

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

### Via uvx (Release wheel)

Substitute `<version>` and provide `GH_TOKEN` in the environment running
MetaMCP (the URL embeds it for the download).

```yaml
servers:
  tee-sniper:
    command: uvx
    args:
      - --from
      - https://${GH_TOKEN}@github.com/<owner>/tee-sniper/releases/download/v<version>/tee_sniper_mcp-<version>-py3-none-any.whl
      - tee-sniper-mcp
    env:
      GH_TOKEN: ghp_...
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

The cross-package roundtrip test (`tests/test_auth.py::test_encrypt_credentials_roundtrip`)
imports `app.services.encryption` from `../api/` to verify our local AES-GCM
encryption produces output the API can decrypt. `mcp/conftest.py` puts `api/`
on `sys.path` for this test; the `redis` dev dependency in `pyproject.toml` is
present because importing through `app/services/__init__.py` triggers the
import of `session_manager.py`, which uses redis.

## Notes

- Requires Python 3.14 (matches `api/`).
- Built on FastMCP ≥ 3.1; tested against 3.2.x. Tools are introspected via
  `mcp.list_tools()`.
- Configuration errors at startup exit with code 2 and print
  `tee-sniper-mcp: configuration error: …` to stderr.
- The package version is derived from the most recent `v*.*.*` git tag via
  `hatch-vcs`. Untagged builds produce a PEP 440 dev version like
  `0.1.dev3+g<sha>`; the build needs git history (`fetch-depth: 0`).
- The console script is `tee_sniper_mcp.cli:main`; it answers `--version`
  before importing the FastMCP runtime stack.
- The Docker image is multi-stage: the builder produces a wheel via
  `python -m build`, the runtime stage installs it. The version is supplied
  by the `VERSION` build-arg (forwarded to `hatch-vcs` via
  `SETUPTOOLS_SCM_PRETEND_VERSION`), so the image does not need `.git/` in
  context. Build context is the repo root —
  `docker build -f mcp/Dockerfile --build-arg VERSION=<x.y.z> .`.
