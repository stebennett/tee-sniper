# Wanted Tee-Times Design

**Status:** Implemented
**Date:** 2026-05-16
**Related:** Extends `api/` (FastAPI service). Follow-up spec will decommission the Go CLI.

## Goal

Let a user register a "wanted tee-time": a persisted request to book a slot
matching some criteria *when it becomes bookable*. A daily worker scans the
registered requests, attempts the ones that are due, records the outcome, and
optionally sends an SMS.

Booking-site slots are released **8 days before play** (e.g. Saturday slots open
the previous Friday). The worker runs once per day, just before release time.

Two kinds of request:

- **One-shot** — a single explicit `target_date`. May be created arbitrarily far
  in advance; it lies dormant until its release window opens, is attempted, then
  reaches a terminal state.
- **Recurring** — a `day_of_week` pattern (optionally capped by `end_date`).
  Re-attempted for each matching occurrence indefinitely until disabled/deleted.

## Non-goals

- **Removing the Go CLI.** A separate follow-up spec covers decommissioning
  `cmd/tee-sniper/`, `pkg/`, `run-teesniper.sh`, and the Go CI. This spec only
  builds the Python worker. However, the worker is deliberately designed at
  **behavioural parity** with the Go CLI (login → find → filter by window →
  random pick → book → add partners → SMS) so the later removal is a clean swap.
- **Multi-user.** Still single-user. API session auth merely gates who can manage
  requests; the encrypted credentials on each record are what the worker uses.
- **MCP exposure.** Adding `create_wanted_slot` / `list_wanted_slots` / etc. MCP
  tools is a follow-up.
- **A UI.** Management is API-only (and MCP later).
- **Per-request dynamic K8s CronJobs.** One fixed daily schedule for all requests.

## Architecture

```
┌──────────────┐  REST /api/wanted   ┌──────────────┐
│  API client  │ ──────────────────► │  FastAPI     │
│  (curl/MCP)  │                     │  routers/    │
└──────────────┘                     │  wanted.py   │
                                     └──────┬───────┘
                                            │  WantedStore (Redis: wanted:{id}, wanted:index)
                                            ▼
                                     ┌──────────────┐
   K8s CronJob (daily) ────────────► │ cli/worker.py│ ── BookingClient ──► booking site
   python -m app.cli.worker          │ run_once()   │ ── Twilio (optional SMS)
                                     └──────────────┘
```

## Data model

`WantedSlot`, stored in Redis at `wanted:{uuid}`, with every id also held in a
`wanted:index` SET so the worker can enumerate without `KEYS`.

| Field | Notes |
|---|---|
| `id` | UUID |
| `kind` | `"one_shot"` \| `"recurring"` |
| `target_date` | ISO date — **one-shot only** |
| `day_of_week` | `mon`..`sun` — **recurring only** |
| `end_date` | optional ISO date cap — recurring only |
| `start_time` / `end_time` | `HH:MM` booking window |
| `num_slots` | 1–4 |
| `partners` | list of partner ids (may be empty) |
| `credentials` | AES-256-GCM blob, identical format to `POST /api/login` |
| `notify` | optional `{to, from}` E.164 phone numbers for SMS |
| `status` | `pending` \| `booked` \| `expired` \| `disabled` |
| `attempts` | bounded list (last ~10) of `{ts, target_date, outcome, booking_id?, error?}` |
| `created_at` / `updated_at` | ISO timestamps |

`status` semantics:

- One-shot collapses to a terminal state: `booked` (succeeded) or `expired`
  (`target_date` passed without success). `disabled` if the user pauses it.
- Recurring stays `pending` until the user sets `disabled` or deletes it;
  per-occurrence outcomes live in `attempts`.

**TTL:** one-shot records get a Redis TTL ≈ 30 days past `target_date`; recurring
records have no TTL (deleted explicitly). Index membership is pruned when a record
expires or is deleted.

Credentials are **never** returned in API responses — only a boolean "set".

## Worker logic — one daily run

`run_once()`:

1. `today = date.today()`, `release_date = today + 8 days`.
2. Enumerate `wanted:index`. For each record decide if **due today**:
   - `disabled` or terminal (`booked`/`expired`) → skip.
   - **One-shot:**
     - `target_date < today` → set `status=expired`, skip.
     - `today ≤ target_date ≤ release_date` → **due** (covers both the
       normal "created early, window now open" case and the "created late,
       already inside the 8-day window" case).
     - `target_date > release_date` → not bookable yet; revisit tomorrow.
   - **Recurring:**
     - `end_date` set and `release_date > end_date` → skip (lapsed; leave as-is).
     - due iff `release_date.weekday() == day_of_week` **and** no existing
       `attempts` entry with `target_date == release_date` and `outcome == booked`.
3. For each due record, run an **attempt** (below). Records are independent — one
   record's failure never aborts the run.

The recurring "already booked this occurrence" guard makes the daily run
idempotent: a second run on the same day won't double-book.

## Attempt logic

Per due record (target date = `release_date`, or `target_date` for one-shots):

1. Decrypt credentials → fresh `BookingClient.login()`. (No Redis session reuse —
   sessions are far too short-lived for a once-a-day worker; login is cheap.)
2. `get_availability(target_date)` → keep bookable slots within
   `[start_time, end_time]`.
3. Pick one **at random** (matches Go CLI; avoids contention on a single slot).
4. `book_time_slot(slot, num_slots)`.
5. For each `partners` id, `add_partner(...)`. Partial success tolerated —
   mirrors existing `PATCH /api/bookings/{id}` semantics.
6. Append an `attempts` entry; if one-shot success, set `status=booked`.
7. Always persist the outcome. If `notify` set, send Twilio SMS (success **and**
   terminal failure).

**Outcomes recorded:**

| Situation | `outcome` | One-shot effect | Recurring effect |
|---|---|---|---|
| Booked | `booked` | `status=booked` (terminal) | logged; occurrence done |
| No slot in window | `no_slots` | stays `pending`, retried until `target_date` passes then `expired` | move on |
| Login failed | `auth_failed` | stays `pending` (user fixes creds via PATCH) | retried next occurrence |
| Upstream 5xx | `upstream_error` | stays `pending`, retry next day | retried |
| Book call failed post-pick | `booking_failed` | stays `pending`, retry next day | retried |

Each attempt is wrapped in its own try/except. No auto-disable on failure — the
daily retry self-heals once the user fixes credentials or the site recovers.

## API surface

New router `app/routers/wanted.py`, prefix `/api/wanted`, all endpoints behind
the existing session-auth dependency.

- `POST /api/wanted` — create. Body is a discriminated union on `kind`:
  - `one_shot`: `target_date, start_time, end_time, num_slots, partners,
    credentials, notify?`
  - `recurring`: `day_of_week, end_date?, start_time, end_time, num_slots,
    partners, credentials, notify?`
  - Returns the full record (credentials redacted).
- `GET /api/wanted` — list all; optional `?status=` filter.
- `GET /api/wanted/{id}` — one record incl. `attempts` history.
- `PATCH /api/wanted/{id}` — mutable: `start_time, end_time, num_slots,
  partners, notify, disabled, credentials`. Immutable: `kind, target_date,
  day_of_week`.
- `DELETE /api/wanted/{id}` — hard delete (also removes from index).

## Code layout

```
api/app/
  models/wanted.py        # pydantic: WantedSlot, Create*/Patch requests, Attempt, Outcome enum
  services/
    wanted_store.py       # Redis CRUD + index management
    notifications.py      # Twilio SMS helper (new)
    worker.py             # run_once(): scan → decide due → attempt → record
  routers/wanted.py       # REST endpoints
  cli/__init__.py
  cli/worker.py           # `python -m app.cli.worker` entrypoint
```

Worker reuses `BookingClient`, `EncryptionService`, `PartnersService`, and the
Redis wiring. `dependencies.py` factory functions are refactored so non-FastAPI
consumers (the CLI worker) can construct the same objects without the request
scope.

## Deployment

Helm additions in `charts/tee-sniper-api/`:

- New `CronJob`: same image as the API, `command: ["python","-m","app.cli.worker"]`,
  schedule from `values.yaml` (default `"30 6 * * *"` — tune to release time).
- Twilio env vars (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and a configurable
  default `from` number) become required **when the CronJob is enabled**.
- Worker is **opt-in** via `values.yaml`, so existing deployments are unchanged
  until explicitly turned on.
- The CronJob can also be triggered ad hoc (`kubectl create job --from=cronjob/...`)
  to force an immediate run — this is the equivalent of the Go CLI's
  cron-passes-the-date invocation.

## Testing

- `wanted_store` CRUD + index integrity against fakeredis.
- **Due-date decision logic exhaustively:** one-shot before window / in window /
  past / already booked / disabled; recurring DoW match / DoW mismatch /
  occurrence already booked / past `end_date`.
- `worker.run_once` with a fake `BookingClient`: success, `no_slots`,
  `auth_failed`, partial partner failure, multi-record run where one fails and
  others still succeed, idempotent second-run-same-day.
- `notifications` SMS helper with a mocked Twilio client (sends on success and
  terminal failure; no-op when `notify` unset).
- CRUD endpoint tests on the existing pytest infra, incl. credential redaction
  and immutable-field rejection on PATCH.

## Future direction (out of scope here)

- Follow-up spec: delete the Go CLI and its CI once this worker is proven at
  parity.
- Follow-up: MCP tools for managing wanted-slots.
