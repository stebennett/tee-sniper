# Manual Test Guide — Wanted Tee-Times

A step-by-step manual verification of the API locally, focused on the new
**wanted tee-times** feature (and the daily worker), plus a baseline check
that the existing app/API still works.

> ⚠️ **Live booking warning.** The booking endpoints and the worker talk to
> the **real** booking site using your real credentials. Steps that can make a
> real reservation are clearly marked **[LIVE]**. The wanted-slot CRUD steps
> (create/list/get/patch/delete) are side-effect-free. The worker step is
> designed so you can verify the whole pipeline **without** making a real
> booking by choosing a target date with no availability.

---

## 0. Prerequisites

- Docker running.
- A `.env` file at the repo root with **real** values:

  ```
  TSA_SHARED_SECRET=<any strong secret string>
  TSA_BASE_URL=https://<your-booking-site>/
  ```
- Valid booking-site credentials (member ID + PIN).
- `python3` available (used only to encrypt credentials and pretty-print JSON).

All commands below are run from the **repository root** unless stated.

---

## 1. Start the stack

```bash
docker compose up -d
docker compose ps
```

Expect both `api` and `redis` services `running` / `healthy`. The dev override
auto-loads (`Dockerfile.dev`, hot-reload, text logs, `TSA_DEBUG=true`).

Tail logs in a second terminal so you can watch requests and the worker:

```bash
docker compose logs -f api
```

---

## 2. Health check

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

**Pass:** HTTP 200, `"status": "healthy"`, `"redis_connected": true`.
If `redis_connected` is false, sessions and wanted-slots won't work — stop and
fix Redis first.

---

## 3. Encrypt credentials & log in

The API never takes a plaintext PIN; it expects the same AES-256-GCM blob
format used everywhere. Generate it with the helper script
`api/encrypt_credentials.py` (it reads `TSA_SHARED_SECRET` from `--secret`,
the environment, or the repo-root `.env`):

```bash
# Prompts for member ID and PIN (PIN input is hidden):
ENCRYPTED=$(api/.venv/bin/python api/encrypt_credentials.py)

# Or non-interactively:
# ENCRYPTED=$(api/.venv/bin/python api/encrypt_credentials.py -u <MEMBER_ID> -p <PIN>)

echo "Encrypted blob length: ${#ENCRYPTED}"
```

> No venv? `python3 api/encrypt_credentials.py` works too, as long as the
> `cryptography` package is importable. Run `api/.venv/bin/python
> api/encrypt_credentials.py --curl` to also print a ready-to-paste
> `{"credentials": "..."}` JSON body. See `--help` for all options.

Log in and capture the bearer token:

```bash
LOGIN=$(curl -s -X POST http://localhost:8000/api/login \
  -H 'Content-Type: application/json' \
  -d "{\"credentials\": \"$ENCRYPTED\"}")
echo "$LOGIN" | python3 -m json.tool
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "TOKEN=$TOKEN"
```

**Pass:** HTTP 200, an `access_token` and `expires_at` returned, `TOKEN` set.

---

## 4. Baseline regression — existing endpoints still work

Confirm the new router didn't break the existing API.

```bash
# Configured partners (auth required)
curl -s http://localhost:8000/api/partners \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Availability for ~8 days out (slots release 8 days before play)
DATE=$(python3 -c "import datetime; print((datetime.date.today()+datetime.timedelta(days=8)).isoformat())")
curl -s "http://localhost:8000/api/$DATE/times" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Pass:** `/api/partners` returns a (possibly empty) list; `/api/{date}/times`
returns `total_count` / `filtered_count` and a `times` array (HTTP 200).

---

## 5. Wanted tee-times — CRUD (safe, no booking side effects)

### 5a. Create a one-shot request

Pick a target date inside the bookable window so the worker would consider it
"due" (today ≤ target ≤ today+8). The `credentials` field is the **same
encrypted blob** from step 3.

```bash
TARGET=$(python3 -c "import datetime; print((datetime.date.today()+datetime.timedelta(days=8)).isoformat())")

CREATE=$(curl -s -X POST "http://localhost:8000/api/wanted?kind=one_shot" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"target_date\":\"$TARGET\",\"start_time\":\"08:00\",\"end_time\":\"10:00\",\"num_slots\":1,\"partners\":[],\"credentials\":\"$ENCRYPTED\"}")
echo "$CREATE" | python3 -m json.tool
WANTED_ID=$(echo "$CREATE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "WANTED_ID=$WANTED_ID"
```

**Pass:** HTTP 201. In the response body verify:
- `"kind": "one_shot"`, `"status": "pending"`, `"target_date"` matches.
- `"has_credentials": true` **and there is NO `credentials` field** (redaction).

### 5b. Create a recurring request

```bash
# day_of_week: Monday=0 … Sunday=6
curl -s -X POST "http://localhost:8000/api/wanted?kind=recurring" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"day_of_week\":5,\"start_time\":\"07:00\",\"end_time\":\"09:00\",\"num_slots\":2,\"partners\":[],\"credentials\":\"$ENCRYPTED\"}" \
  | python3 -m json.tool
```

**Pass:** HTTP 201, `"kind": "recurring"`, `"day_of_week": 5`, `target_date` null.

### 5c. List & filter

```bash
curl -s http://localhost:8000/api/wanted \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
curl -s "http://localhost:8000/api/wanted?status=pending" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Pass:** the list contains both records; the `?status=pending` filter returns
them too; no `credentials` field on any item.

### 5d. Get one / 404

```bash
curl -s "http://localhost:8000/api/wanted/$WANTED_ID" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
curl -s -o /dev/null -w "%{http_code}\n" \
  "http://localhost:8000/api/wanted/does-not-exist" \
  -H "Authorization: Bearer $TOKEN"
```

**Pass:** the first returns the record (200, with empty `attempts`); the
second prints `404`.

### 5e. Patch — update window, then disable & re-enable

```bash
curl -s -X PATCH "http://localhost:8000/api/wanted/$WANTED_ID" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"start_time":"09:00","disabled":true}' | python3 -m json.tool

curl -s -X PATCH "http://localhost:8000/api/wanted/$WANTED_ID" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"disabled":false}' | python3 -m json.tool
```

**Pass:** first response `"status": "disabled"` and `"start_time": "09:00"`;
second response `"status": "pending"` (re-enabled).

### 5f. Validation (expect 422, not 500)

```bash
# Missing target_date for a one-shot
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  "http://localhost:8000/api/wanted?kind=one_shot" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"start_time":"08:00","end_time":"10:00","credentials":"x"}'

# Patch into an invalid window (start after stored end)
curl -s -o /dev/null -w "%{http_code}\n" -X PATCH \
  "http://localhost:8000/api/wanted/$WANTED_ID" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"start_time":"23:00"}'
```

**Pass:** both print `422` (clean validation error, **not** 500).

---

## 6. Inspect Redis (optional)

Confirm persistence and the index set:

```bash
docker compose exec redis redis-cli KEYS 'wanted:*'
docker compose exec redis redis-cli SMEMBERS wanted:index
docker compose exec redis redis-cli TTL "wanted:$WANTED_ID"   # one-shot: >0 (≈ target+30d)
```

**Pass:** a `wanted:<id>` key per request, all ids present in `wanted:index`,
the one-shot key has a positive TTL.

---

## 7. Run the worker

The worker logs in, finds a slot in the window, and **books it for real**.
To verify the **full pipeline without a real booking**, first point the
one-shot at a date with **no availability** so the outcome is `no_slots`.

### 7a. Safe pipeline test (no booking)

```bash
# A date far in the future is not yet bookable -> no slots -> no booking made,
# but login + availability fetch + decision + attempt recording all execute.
FUTURE=$(python3 -c "import datetime; print((datetime.date.today()+datetime.timedelta(days=8)).isoformat())")
# (Use a real near-term date whose tee sheet you know is full/empty, or keep
#  the default 8-days-out date and a narrow window unlikely to have slots.)

docker compose exec api python -m app.cli.worker
```

Watch the `docker compose logs -f api` output for
`Worker run starting` … `Worker run finished`. Then inspect the record:

```bash
curl -s "http://localhost:8000/api/wanted/$WANTED_ID" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Pass (safe path):** `attempts` now has one entry with an `outcome` such as
`no_slots`, `auth_failed`, or `upstream_error`; `status` is still `pending`
(one-shot is not consumed on a non-booking outcome). This proves the
end-to-end worker pipeline runs.

> If `outcome` is `auth_failed`, the credentials blob in the wanted record
> didn't decrypt — confirm you used the **same** `$ENCRYPTED` value and the
> same `TSA_SHARED_SECRET` the API container runs with.

### 7b. **[LIVE]** Real booking via the worker (only if you intend to book)

If you want to verify an actual booking: set the one-shot's window to a time
you know is bookable on a date within the 8-day release window, then run
`docker compose exec api python -m app.cli.worker` again. On success the
record's `status` becomes `booked` and the latest `attempt` has
`outcome: booked` with a `booking_id`. **This is a real reservation —
cancel it on the booking site afterwards if it was only a test.**

Idempotency check: run the worker a second time the same day — a recurring
slot must **not** re-book the same occurrence (no new `booked` attempt for the
same `target_date`); a one-shot already `booked` is skipped.

### 7c. SMS notification (optional)

If you want to test SMS, recreate a wanted slot with a `notify` block and set
the Twilio env (`TSA_TWILIO_ACCOUNT_SID`, `TSA_TWILIO_AUTH_TOKEN`,
`TSA_TWILIO_FROM_NUMBER`) on the API/worker container:

```json
{ "...": "...", "notify": { "to": "+1555...", "from": "+1555..." } }
```

**Pass:** an SMS is received on success or terminal failure. With Twilio env
unset, the worker must run fine and simply send nothing (no error).

---

## 8. Clean up

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE \
  "http://localhost:8000/api/wanted/$WANTED_ID" \
  -H "Authorization: Bearer $TOKEN"          # expect 204

curl -s http://localhost:8000/api/wanted \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool   # delete the recurring one too

docker compose down            # add -v to also wipe the redis volume
```

**Pass:** delete returns `204`; a second GET of the id returns `404`; the
index no longer lists the deleted id.

---

## Result checklist

- [ ] Health 200, Redis connected
- [ ] Login returns a token
- [ ] Existing `/api/partners` and `/api/{date}/times` still work
- [ ] Create one-shot & recurring (201, credentials redacted)
- [ ] List / status filter / get / 404
- [ ] Patch updates window; disable→`disabled`; re-enable→`pending`
- [ ] Invalid input returns 422 (not 500)
- [ ] Redis holds `wanted:*` keys + `wanted:index`; one-shot has TTL
- [ ] Worker runs end-to-end and records an attempt
- [ ] (Optional) live booking / idempotency / SMS
- [ ] Delete returns 204; record gone from index
