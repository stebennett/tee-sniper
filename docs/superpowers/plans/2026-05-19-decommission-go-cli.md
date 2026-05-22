# Decommission the Go CLI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the Go CLI and everything that exists solely to build, test, release, or document it, leaving the Python API + worker + MCP server as the sole product.

**Architecture:** Pure deletion + workflow edits + documentation rewrite. No new code. There is no shared library between Go and Python (`pkg/crypto` and `api/app/services/encryption.py` are independent), so deletion is non-invasive. "Tests" here means verification commands (grep for dangling references, run the surviving Python/MCP suites, lint the workflow YAML, render the Helm chart).

**Tech Stack:** Git, GitHub Actions YAML, Python (pytest), uv (MCP), Helm.

**Spec:** `docs/superpowers/specs/2026-05-19-decommission-go-cli-design.md`

**Prerequisite (manual, NOT part of this PR):** Before merging the PR this plan produces, the maintainer must push a final `v*.*.*` tag from `main` while the Go code is still present, so `release.yml` produces the last archival Go binary + Go Docker image. The PR description must state this prerequisite. The plan below assumes that tag has been (or will be) cut from a commit that predates the deletion.

**Branch / worktree:** Work happens in the existing worktree `decommission-go-cli` (branch `worktree-decommission-go-cli`), already created off the updated `main`.

---

## File Structure

Files to **delete**:
- `cmd/` (whole tree)
- `pkg/` (whole tree: `clients/`, `config/`, `crypto/`, `logger/`, `models/`, `teetimes/`, `utils/`)
- `vendor/` (whole tree)
- `go.mod`, `go.sum`
- `run-teesniper.sh`
- `Dockerfile` (repo-root, Go-only)
- `.dockerignore` (only describes the root Go build context — orphaned once `Dockerfile` is gone; `docker-compose.yml` uses `./api` and `./api/Dockerfile`, which have their own ignore rules)
- `testdata/` (HTML fixtures consumed only by Go tests in `pkg/clients`; the sole non-Go reference is the historical `docs/DOCKER_PLAN.md`, left as-is)
- `.github/workflows/build.yml` (Go-only build/test workflow)

Files to **edit**:
- `.github/workflows/release.yml` — remove Go binary + Go Docker image; keep API + MCP.
- `.gitignore` — drop Go-only ignore lines.
- `README.md` — full Python-centric rewrite.
- `CLAUDE.md` — remove Go sections.

Files explicitly **left as-is** (historical records / Python-only):
- `docs/API_MIGRATION_PLAN.md`, `docs/DOCKER_PLAN.md`, `docs/PHASE2_REDIS_PLAN.md`, and all other `docs/` plan/spec files.
- `docker-compose.yml`, `docker-compose.override.yml` (Python API only — build context `./api`).
- `.env.example` (already Python-only, `TSA_` prefix, no `TS_*`/Twilio vars — see Task 7 verification).
- `charts/` (already Python-only).

---

## Task 1: Delete Go source, vendor, and module files

**Files:**
- Delete: `cmd/`, `pkg/`, `vendor/`, `go.mod`, `go.sum`

- [ ] **Step 1: Confirm nothing outside Go references these paths**

Run:
```bash
grep -rn --exclude-dir=docs --exclude-dir=.git -e 'cmd/tee-sniper' -e '\bpkg/clients\b' -e '\bpkg/teetimes\b' . | grep -vE '\.go:' | grep -vE '^\./(cmd|pkg|vendor)/'
```
Expected: no output (any hits in `docs/` are historical and excluded; if a hit appears in `README.md`/`CLAUDE.md` that is expected — those are rewritten in Tasks 5–6).

- [ ] **Step 2: Delete the trees and module files**

Run:
```bash
git rm -r -q cmd pkg vendor go.mod go.sum
```

- [ ] **Step 3: Verify removal**

Run:
```bash
ls cmd pkg vendor go.mod go.sum 2>&1
```
Expected: "No such file or directory" for every path.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove Go CLI source, vendor, and module files"
```

---

## Task 2: Delete Go build/run tooling

**Files:**
- Delete: `run-teesniper.sh`, `Dockerfile`, `.dockerignore`, `testdata/`

- [ ] **Step 1: Confirm `testdata/` is Go-only**

Run:
```bash
grep -rl "testdata" api/ mcp/ charts/ 2>/dev/null
```
Expected: no output (Go tests were already deleted in Task 1; the only other reference is `docs/DOCKER_PLAN.md`, which is intentionally left as a historical record).

- [ ] **Step 2: Confirm compose does not use the root Dockerfile/.dockerignore**

Run:
```bash
grep -nE 'dockerfile:|context:' docker-compose.yml docker-compose.override.yml
```
Expected: all `context:` values are `./api`, all `dockerfile:` values are `Dockerfile`/`Dockerfile.dev` resolved against `./api` — none reference the repo root. (This confirms deleting the root `Dockerfile`/`.dockerignore` does not affect compose.)

- [ ] **Step 3: Delete the files**

Run:
```bash
git rm -r -q run-teesniper.sh Dockerfile .dockerignore testdata
```

- [ ] **Step 4: Verify removal**

Run:
```bash
ls run-teesniper.sh Dockerfile .dockerignore testdata 2>&1
```
Expected: "No such file or directory" for every path.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove Go build/run tooling (run script, Dockerfile, testdata)"
```

---

## Task 3: Delete the Go CI workflow

**Files:**
- Delete: `.github/workflows/build.yml`

- [ ] **Step 1: Confirm no other workflow references `build.yml`**

Run:
```bash
grep -rn "build.yml" .github/
```
Expected: no output (workflows do not call each other by filename here).

- [ ] **Step 2: Delete it**

Run:
```bash
git rm -q .github/workflows/build.yml
```

- [ ] **Step 3: Verify the remaining workflows are Python/MCP/Helm only**

Run:
```bash
ls .github/workflows/
```
Expected: `api-build.yml  helm-chart.yml  mcp-build.yml  release.yml` (no `build.yml`).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "ci: remove Go-only build workflow"
```

---

## Task 4: Strip Go binary + Go Docker image from release.yml

**Files:**
- Modify: `.github/workflows/release.yml`

The current file has these Go-specific blocks (verify line numbers with `grep -n` before editing — earlier tasks do not touch this file, so the spec's reference line numbers should still hold, but always confirm):

1. `Set up Go` step (uses `actions/setup-go@v5`, `go-version: '1.26'`).
2. `Build for Linux amd64` step (`GOOS=linux GOARCH=amd64 go build -o tee-sniper-linux-amd64 ./cmd/tee-sniper`).
3. `Upload Linux Binary` step (`actions/upload-release-asset@v1`, `asset_name: tee-sniper-linux-amd64`).
4. `Extract metadata for Go Docker image` step (`id: meta`, `images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}`).
5. `Build and push Go Docker image` step (`docker/build-push-action@v7`, `context: .`, `tags: ${{ steps.meta.outputs.tags }}`).

All other steps (Python setup, uv, MCP wheel/sdist build + verify + upload, `Create Release`, Docker login steps, API image meta + build/push, MCP image meta + build/push) are kept **unchanged**.

- [ ] **Step 1: Locate the exact blocks to remove**

Run:
```bash
grep -n -e 'Set up Go' -e 'Build for Linux amd64' -e 'Upload Linux Binary' -e 'metadata for Go Docker image' -e 'push Go Docker image' .github/workflows/release.yml
```
Expected: five matching step headers, confirming the blocks exist.

- [ ] **Step 2: Remove the `Set up Go` step**

Delete these lines (the step and its trailing blank line):
```yaml
    - name: Set up Go
      uses: actions/setup-go@v5
      with:
        go-version: '1.26'
```

- [ ] **Step 3: Remove the `Build for Linux amd64` step**

Delete:
```yaml
    - name: Build for Linux amd64
      run: |
        GOOS=linux GOARCH=amd64 go build -o tee-sniper-linux-amd64 ./cmd/tee-sniper
```

- [ ] **Step 4: Remove the `Upload Linux Binary` step**

Delete:
```yaml
    - name: Upload Linux Binary
      uses: actions/upload-release-asset@v1
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      with:
        upload_url: ${{ steps.create_release.outputs.upload_url }}
        asset_path: ./tee-sniper-linux-amd64
        asset_name: tee-sniper-linux-amd64
        asset_content_type: application/octet-stream
```

- [ ] **Step 5: Remove the Go Docker image metadata + build/push steps**

Delete both consecutive steps:
```yaml
    - name: Extract metadata for Go Docker image
      id: meta
      uses: docker/metadata-action@v6
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=semver,pattern={{version}}
          type=semver,pattern={{major}}.{{minor}}
          type=raw,value=latest

    - name: Build and push Go Docker image
      uses: docker/build-push-action@v7
      with:
        context: .
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
```

- [ ] **Step 6: Confirm no remaining reference to the removed `meta` step or Go**

Run:
```bash
grep -n -e 'steps.meta\.' -e 'setup-go' -e 'go build' -e 'tee-sniper-linux-amd64' -e 'Go Docker image' .github/workflows/release.yml
```
Expected: no output. (`steps.meta-api.` and `steps.meta-mcp.` must still be present and are fine — the pattern `steps.meta\.` with the literal dot does not match them.)

- [ ] **Step 7: Validate the workflow YAML parses**

Run:
```bash
python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/release.yml')); print('YAML OK')"
```
Expected: `YAML OK`

- [ ] **Step 8: Confirm the kept artefacts are still wired**

Run:
```bash
grep -n -e 'IMAGE_NAME }}-api' -e 'IMAGE_NAME }}-mcp' -e 'Upload MCP wheel' -e 'Upload MCP sdist' -e 'Create Release' .github/workflows/release.yml
```
Expected: matches for the API image, MCP image, MCP wheel upload, MCP sdist upload, and Create Release — proving the surviving release flow is intact.

- [ ] **Step 9: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: drop Go binary and Go Docker image from release workflow"
```

---

## Task 5: Trim Go-only entries from .gitignore

**Files:**
- Modify: `.gitignore`

Current `.gitignore` is the GitHub Go template plus a few project lines. Remove the Go-specific lines; keep the project lines (`.env`, `.worktrees/`, Helm subchart ignores).

- [ ] **Step 1: Replace the file with the Go-stripped version**

Write `.gitignore` with exactly this content:
```gitignore
.env

.worktrees/

# Helm: don't commit pulled subcharts (Chart.lock pins them)
charts/*/charts/
charts/*/*.tgz
```

- [ ] **Step 2: Verify no Go remnants remain**

Run:
```bash
grep -nE 'go\.work|\*\.test|\*\.exe|Golang|go coverage|vendor/' .gitignore
```
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: drop Go-only .gitignore entries"
```

---

## Task 6: Rewrite README.md (Python-centric)

**Files:**
- Modify: `README.md` (full replacement)

The current README is entirely Go-centric (headings: Features → Prerequisites → Installation (From Source/Releases/Docker) → Configuration (Twilio/App/CLI options) → Usage (Help/Basic/Partners/Dry Run/Convenience Script) → Project Structure → API Service → MCP server → How It Works → Development (Go tests/build/deps) → CI/CD → Roadmap → License). Replace the whole file.

- [ ] **Step 1: Write the new README**

Replace the entire contents of `README.md` with:

````markdown
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
````

- [ ] **Step 2: Verify no Go content remains in README**

Run:
```bash
grep -niE 'go run|go build|go test|cmd/tee-sniper|run-teesniper|jessevdk|goquery|GOOS=' README.md
```
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README around the Python API, worker, and MCP server"
```

---

## Task 7: Strip Go sections from CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

Remove the Go-specific content while keeping Python API, worker, MCP, Helm, and migration-history guidance. Target sections (verify with `grep -n '^#' CLAUDE.md` first):

- `### Running the Application` — replace Go run commands with the API + worker run commands.
- `### Testing` — remove the two Go test lines (`go test ./...`, `go test ./pkg/teetimes/`); keep all Python/MCP/Redis lines.
- `### Building` — remove entirely (Go `go build`).
- `### Project Structure` — remove the **Go CLI** bullet block; keep the **Python API** block.
- `### Core Components` — remove `Main Application Flow`, `Configuration` (go-flags), `Tee Time Logic`, and `External Dependencies` (Twilio Go SDK / goquery / go-flags) subsections (all describe Go internals).
- `### Environment Variables` — this block documents the Go app's `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`; replace with a one-line pointer to `.env.example` / `api/app/config.py` (`TSA_`-prefixed, incl. `TSA_TWILIO_*`).
- `### GitHub Actions Integration` — update: remove `build.yml`; describe `api-build.yml`, `mcp-build.yml`, `helm-chart.yml`, `release.yml` (API + MCP artefacts only, no Go binary/image).
- Keep unchanged: `## Testing Workflow`, `## API Migration Workflow`, `## Wanted Tee-Times`, `## Docker Migration Workflow`, `### MCP Server (Local)`, `### MCP Plan History` (historical/Python).

- [ ] **Step 1: Confirm current heading layout**

Run:
```bash
grep -n '^#' CLAUDE.md
```
Expected: matches the layout described above (use it to locate exact line ranges).

- [ ] **Step 2: Edit `### Running the Application`**

Replace the section body (the `bash` block with `go run cmd/tee-sniper/main.go ...`, `./run-teesniper.sh`, and the all-parameters example) with:
````markdown
```bash
# Run the API (FastAPI)
cd api && .venv/bin/python -m uvicorn app.main:app --reload

# Or the full stack via Docker Compose
docker compose up

# Run the wanted-slot worker once
cd api && .venv/bin/python -m app.cli.worker
```
````

- [ ] **Step 3: Edit `### Testing`**

Remove these two lines and their preceding comment lines:
```bash
# Run Go tests
go test ./...

# Run Go tests for specific package
go test ./pkg/teetimes/
```
Keep every other line in the section (Python API tests, specific test file, worker one-shot, the Redis/`TSA_REQUIRE_REDIS` paragraph).

- [ ] **Step 4: Remove `### Building`**

Delete the entire `### Building` heading and its fenced block:
```
### Building
```bash
# Build the application
go build -o tee-sniper cmd/tee-sniper/main.go
```
```

- [ ] **Step 5: Edit `### Project Structure`**

Delete the `**Go CLI:**` bullet list (entry point + `pkg/...` lines). Keep the `**Python API** (`api/`):` bullet list. If the heading now has only the Python block, leave the heading.

- [ ] **Step 6: Edit `### Core Components`**

Delete these subsections in full (they document Go internals):
- `**Main Application Flow** (cmd/tee-sniper/main.go):` and its numbered list
- `**Configuration** (pkg/config/config.go):` paragraph
- `**Tee Time Logic** (pkg/teetimes/teetimes.go):` and its bullet list
- `**External Dependencies**:` bullet list (Twilio Go SDK, goquery, go-flags)

If nothing meaningful remains under `### Core Components`, remove the heading too.

- [ ] **Step 7: Edit `### Environment Variables`**

Replace the section body (which lists `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` for the Go app) with:
```markdown
All configuration is `TSA_`-prefixed and read by `api/app/config.py`
(pydantic-settings). See `.env.example` for the common variables and
`api/app/config.py` for the full set, including optional
`TSA_TWILIO_ACCOUNT_SID` / `TSA_TWILIO_AUTH_TOKEN` /
`TSA_TWILIO_FROM_NUMBER` for SMS notifications.
```

- [ ] **Step 8: Edit `### GitHub Actions Integration`**

Replace the section body with:
```markdown
The repository includes CI workflows in `.github/workflows/`:
- `api-build.yml` - API build/test (provisions Redis, sets `TSA_REQUIRE_REDIS=1`)
- `mcp-build.yml` - MCP build/test
- `helm-chart.yml` - Helm chart lint/package
- `release.yml` - on `v*.*.*` tags, builds and pushes the API image
  (`ghcr.io/<repo>-api`), the MCP image (`ghcr.io/<repo>-mcp`), and the
  MCP wheel + sdist as release assets
```

- [ ] **Step 9: Verify no Go content remains**

Run:
```bash
grep -niE 'go run|go build|go test|cmd/tee-sniper|run-teesniper|go-flags|goquery|jessevdk|twilio go sdk|pkg/config|pkg/teetimes' CLAUDE.md
```
Expected: no output.

- [ ] **Step 10: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: remove Go CLI sections from CLAUDE.md"
```

---

## Task 8: Full verification sweep

**Files:** none (verification only)

- [ ] **Step 1: No dangling Go references anywhere outside historical docs/specs**

Run:
```bash
grep -rn --exclude-dir=.git \
  -e 'go run' -e 'go build' -e 'go test' -e 'cmd/tee-sniper' \
  -e 'tee-sniper-linux-amd64' -e 'GOOS=' -e 'jessevdk' \
  . | grep -vE '^\./docs/' | grep -vE '^\./\.git'
```
Expected: no output. (Hits under `docs/` — historical plan/spec files and this plan/spec — are expected and excluded. If anything else appears, fix it before continuing.)

- [ ] **Step 2: No reference to the retired Go Docker image**

Run:
```bash
grep -rn --exclude-dir=.git 'IMAGE_NAME }}\b' .github/workflows/release.yml
```
Expected: every match is `IMAGE_NAME }}-api` or `IMAGE_NAME }}-mcp` — no bare `${{ env.IMAGE_NAME }}` (the Go image) remains.

- [ ] **Step 3: Python API suite is green**

Run:
```bash
cd api && .venv/bin/python -m pytest tests/ -v
```
Expected: all tests pass (session integration tests may SKIP if no local Redis — that is acceptable locally).

- [ ] **Step 4: MCP suite is green (encryption roundtrip survives without Go)**

Run:
```bash
cd mcp && uv sync --all-extras --dev && uv run pytest
```
Expected: all tests pass, including the encryption roundtrip test in `mcp/tests/test_auth.py`.

- [ ] **Step 5: Workflow YAML is valid and Go-free**

Run:
```bash
for f in .github/workflows/*.yml; do python3 -c "import yaml,sys; yaml.safe_load(open('$f')); print('OK $f')"; done
ls .github/workflows/build.yml 2>&1
```
Expected: `OK` for every remaining workflow; `build.yml` reported as "No such file or directory".

- [ ] **Step 6: Helm chart still renders (no collateral damage)**

Run:
```bash
helm template charts/tee-sniper-api >/dev/null && echo "helm OK"
```
Expected: `helm OK` (if `helm` is unavailable in the environment, note it and skip — the chart was already Python-only and untouched by this plan).

- [ ] **Step 7: Repository builds no Go (sanity)**

Run:
```bash
ls go.mod go.sum vendor cmd pkg Dockerfile run-teesniper.sh .dockerignore testdata 2>&1
```
Expected: "No such file or directory" for every path.

- [ ] **Step 8: Final verification commit (only if any fix was needed)**

If steps 1–7 surfaced an issue and you fixed it, commit the fix:
```bash
git add -A
git commit -m "chore: address verification findings for Go decommission"
```
Otherwise, no commit — verification passed clean.

---

## Done

When all tasks are complete: the controller (not implementer subagents)
pushes the branch and opens a **single combined PR**. The PR description
MUST state the prerequisite: *"A final archival `v*.*.*` release tag must
be cut from `main` (with Go code still present) BEFORE this PR is merged —
it produces the last Go binary + Go Docker image as the rollback point."*
````
