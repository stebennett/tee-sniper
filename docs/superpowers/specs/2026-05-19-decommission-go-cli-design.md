# Decommission the Go CLI — Design

**Date:** 2026-05-19
**Status:** Approved (brainstorming)

## Context

The original tee-sniper product was a Go CLI (`cmd/tee-sniper/`, `pkg/`)
driven by `run-teesniper.sh` and an external cron. Its functionality has
been fully reimplemented in the Python stack:

- The FastAPI service (`api/`) + Redis handle credentials, sessions, and
  booking.
- The `wanted` API (`/api/wanted`) registers persisted booking requests
  (one-shot by date, or recurring by day-of-week).
- A daily worker (`python -m app.cli.worker`, deployed as the opt-in
  `worker` Helm CronJob in `charts/tee-sniper-api`) processes due requests,
  books a matching slot, records the outcome, and optionally sends a Twilio
  SMS.

The Python worker + `wanted` API is the replacement for the Go CLI:
scheduling that used to be an external cron around the Go binary is now
handled inside the `wanted` API and its worker CronJob. The Go code is now
dead weight: separate build, separate CI, separate Docker image, a
Go-centric README, and a duplicated AES-GCM implementation.

There is no shared library between the Go and Python code. `pkg/crypto`
and `api/app/services/encryption.py` are independent implementations of
the same AES-256-GCM scheme; the MCP server has its own third copy.

## Goal

Remove the Go CLI and everything that exists solely to build, test,
release, or document it, leaving the Python API + worker + MCP server as
the sole product. Preserve a final archival snapshot of the Go CLI before
deletion.

## Non-Goals

- No behavior change to the Python API, worker, or MCP server.
- No rewrite of historical plan docs (they are records of completed work).
- No GoReleaser introduction or Docker image aliasing.

## Sequencing

This is a two-step decommission. Step 1 is a manual action by the
maintainer; step 2 is the PR produced from this spec's implementation
plan.

1. **Final archival release (manual, before merging the decommission
   PR).** From `main` (Go code still present), push a `v*.*.*` tag.
   `release.yml` builds the Go binary (`tee-sniper-linux-amd64`) and the
   `ghcr.io/<repo>` Docker image one last time and attaches them to the
   GitHub Release. This is the rollback point.
2. **Decommission PR (single combined PR).** Deletes Go code, strips Go
   CI, retires the Go Docker image, rewrites docs. Merged only **after**
   the archival tag exists.

**Ordering constraint:** the tag must be cut while Go code is still on
`main`. The PR description must state this prerequisite explicitly.

The 3 deliverables ship as one combined PR (not phased), consistent with
the project preference for a single PR on multi-step work.

## Changes

### Delete: Go source & build artifacts

- `cmd/` — entry point and tests.
- `pkg/` — all packages: `clients/`, `config/`, `models/`, `teetimes/`,
  `crypto/`, `logger/`, `utils/` (including `mocks/`).
- `go.mod`, `go.sum`, `vendor/`.
- `run-teesniper.sh` — Go convenience wrapper.
- `Dockerfile` (repo root) — Go-only multi-stage build. The API and MCP
  have their own Dockerfiles (`api/`, `mcp/`); the root one is Go-only.

### Edit: environment files

- `.env` / `.env.example` — remove Go-only entries (`TS_USERNAME`,
  `TS_PIN`, `TS_BASEURL`, and any other `TS_*` CLI params). Twilio vars
  (`TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN`): keep iff the Python worker
  still consumes them — verify against `api/app/config.py` and the worker
  before removing. Keep whatever the Python side needs.

### Crypto

`pkg/crypto/encrypt.go` is deleted with the rest of `pkg/`. The Python API
and MCP each retain their own independent AES-GCM implementation, so
nothing breaks at runtime. The only loss is the Go side of the
cross-language roundtrip guard; the surviving MCP↔API Python roundtrip
test (`mcp/tests/test_auth.py`) still guards drift between the two
remaining implementations.

### CI / release workflows

- **Delete `.github/workflows/build.yml`.** It only runs `go build ./...`
  / `go test ./...`, path-filtered to Go sources. The Python API has
  `api-build.yml`; MCP has its own workflow. Nothing else references
  `build.yml`.
- **Edit `.github/workflows/release.yml`** (keep the file):
  - Remove the Go binary build step
    (`GOOS=linux GOARCH=amd64 go build -o tee-sniper-linux-amd64
    ./cmd/tee-sniper`) and its release-asset upload.
  - Remove the standalone `ghcr.io/<repo>` Docker image build/push (the
    Go image). The image is **retired** — no alias, no pointer.
  - Keep the API image (`ghcr.io/<repo>-api`) and the MCP image + wheel
    build/push steps untouched.

Net effect after merge: a `v*.*.*` tag produces the API image + MCP image
+ MCP wheel. No Go binary, no Go Docker image.

### Documentation

- **`README.md` — full rewrite, Python-centric:**
  - *What it is:* a tee-time auto-booking system. FastAPI service + Redis
    store credentials/sessions; the `wanted` API registers persisted
    booking requests (one-shot by date or recurring by day-of-week); a
    daily worker CronJob processes due requests and books, with optional
    Twilio SMS.
  - *Deployment:* the `charts/tee-sniper-api` Helm chart (API + Redis +
    opt-in `worker` CronJob) — the replacement for the old
    `run-teesniper.sh`/cron-driven Go binary.
  - *API reference:* login + booking + `wanted` endpoints, pointing to
    deeper docs.
  - *MCP server:* brief section pointing to `mcp/README.md`.
  - *Local dev / testing:* `cd api && .venv/bin/python -m pytest tests/`,
    `cd mcp && uv run pytest`, the worker one-shot command. All `go
    run`/Go build/Go dependency content removed.
  - Drop the "Decommission the Go CLI" roadmap bullet (now done); keep the
    other roadmap items.
- **`CLAUDE.md` — remove Go sections:** Go run/test/build commands; the Go
  "Project Structure", "Main Application Flow", "Tee Time Logic", and Go
  environment-variable blocks. Keep the Python API, worker, MCP, Helm, and
  migration-history sections.
- **Historical plan docs** (`docs/API_MIGRATION_PLAN.md`,
  `docs/DOCKER_PLAN.md`, etc.) — left as-is. They record completed
  migrations; rewriting them would erase project history. This spec is the
  forward-looking record.

## Verification

The Go test suite disappears, so completeness/safety is verified by:

1. **No dangling Go references.** Grep the repo for `go run`, `go build`,
   `go test`, `cmd/tee-sniper`, `pkg/`, `go.mod`, `tee-sniper-linux-amd64`,
   and the old `ghcr.io/<repo>` image — zero hits outside historical plan
   docs and this spec.
2. **Python suite green:** `cd api && .venv/bin/python -m pytest tests/ -v`
   passes.
3. **MCP suite green:** `cd mcp && uv run pytest` passes — confirms the
   encryption roundtrip test still works without the Go side.
4. **Workflow sanity:** `release.yml` is valid YAML with no references to
   deleted steps/paths; no remaining workflow references the deleted
   `build.yml`.
5. **Helm chart intact:** `helm template charts/tee-sniper-api` succeeds
   (chart was already Python-only; this confirms no collateral damage).

## Rollback

The archival `v*.*.*` tag (step 1) carries the last Go binary + Go Docker
image as GitHub Release assets. The full Go source remains in git history
prior to the decommission commit. Recovery = check out the archival tag or
revert the decommission PR.
