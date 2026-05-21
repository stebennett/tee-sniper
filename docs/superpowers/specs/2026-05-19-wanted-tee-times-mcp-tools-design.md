# Wanted Tee-Time MCP Tools — Design

Date: 2026-05-19

## Goal

Expose the persisted auto-booking ("wanted tee-times") feature through the
local MCP server so an LLM/user can create, inspect, edit, pause, and delete
wanted-slot requests without leaving Claude Desktop / MetaMCP.

Background:

- Wanted API spec: `docs/superpowers/specs/2026-05-16-wanted-tee-times-design.md`
- Wanted router: `api/app/routers/wanted.py` (`/api/wanted`, session-authed)
- MCP server: `mcp/src/tee_sniper_mcp/` (stdio FastMCP, REST client)

## Scope & Architecture

Add **7 tools** to the existing `Tools` class
(`mcp/src/tee_sniper_mcp/tools.py`), registered in `server.py`. Each tool
proxies a `/api/wanted` endpoint via the existing `ApiClient` (lazy login +
in-memory token cache + single 401 retry already implemented in
`api_client.py` / `auth.py`).

No new infrastructure. Same conventions as the existing 4 tools:

- Return a JSON-friendly `dict` on success.
- On any failure return `{"error": "..."}` (optionally with extra keys) —
  **never raise** out of a tool method.
- Local parse failures short-circuit before any HTTP call.

Tools:

1. `create_one_shot_wanted`
2. `create_recurring_wanted`
3. `list_wanted`
4. `get_wanted`
5. `update_wanted`
6. `set_wanted_enabled`
7. `delete_wanted`

Existing 4 tools (`find_tee_times`, `book_tee_time`, `list_partners`,
`add_partners`) are unchanged.

## Tool Signatures

### `create_one_shot_wanted(target_date, start_time, end_time, num_slots=1, partners=None)`

- `POST /api/wanted?kind=one_shot`.
- `target_date`: natural-language (`'next saturday'`, `'in 3 days'`,
  `'tomorrow'`) or ISO `YYYY-MM-DD`, via existing `parse_date`.
- `start_time` / `end_time`: via `parse_time` → canonical `HH:MM`.
- `partners`: optional list of partner ids (≤3; API enforces).
- `credentials`: **auto-encrypted from config** using `encrypt_credentials`
  (same AES-256-GCM scheme as login) from `TSA_USERNAME` / `TSA_PIN` /
  `TSA_SHARED_SECRET`. Never a tool argument; the LLM/user never sees it.
- Returns the created slot summary (see Response Shaping).

### `create_recurring_wanted(day_of_week, start_time, end_time, num_slots=1, partners=None, end_date=None)`

- `POST /api/wanted?kind=recurring`.
- `day_of_week`: accepts `"saturday"` / `"sat"` / `"6"` / `6` →
  normalized to int `0–6`. Convention: **0 = Monday … 6 = Sunday**
  (matches `WantedSlot.day_of_week`, `ge=0, le=6`).
- `end_date`: optional, natural-language or ISO; omit for open-ended.
- `start_time` / `end_time` / `partners` / credentials: as above.

### `list_wanted(status=None)`

- `GET /api/wanted`, optional `status` filter ∈
  `pending` | `booked` | `expired` | `disabled`.
- Invalid `status` value → `{"error": ...}` before the HTTP call.
- Returns `{"wanted": [<summary>, ...]}` (trimmed; see Response Shaping).

### `get_wanted(wanted_id)`

- `GET /api/wanted/{id}`.
- Returns the full slot including `attempts` history.
- 404 → `{"error": "wanted slot not found"}`.

### `update_wanted(wanted_id, start_time=None, end_time=None, num_slots=None, partners=None)`

- `PATCH /api/wanted/{id}`. Only fields explicitly provided are sent
  (omitted args are not included in the patch body).
- `start_time` / `end_time` parsed via `parse_time` when provided.
- **Not** exposed: `notify` (deliberately out of scope), `credentials`
  (re-deriving from config would be a no-op), and the immutable
  `kind` / `target_date` / `day_of_week`.
- 404 / 422 → `{"error": ...}` (API 422 detail surfaced verbatim).

### `set_wanted_enabled(wanted_id, enabled)`

- `PATCH /api/wanted/{id}` with body `{"disabled": not enabled}`.
- `enabled=False` → API sets status `disabled`; `enabled=True` →
  API restores a disabled slot to `pending`.
- Returns the updated slot summary.

### `delete_wanted(wanted_id)`

- `DELETE /api/wanted/{id}`. 204 → `{"deleted": true, "id": wanted_id}`.
- 404 → `{"error": "wanted slot not found"}`.

## Day-of-Week Normalization

A helper (placed in `dates.py` alongside the existing parsers) maps
day input → `int 0–6`:

- Full names (`"monday"`), 3-letter abbreviations (`"mon"`),
  case-insensitive.
- Numeric strings (`"0"`) and ints (`0`) passed through with range check.
- Anything else → `DateParseError`.

Convention **0 = Monday … 6 = Sunday**. During implementation, verify this
against the worker's `api/app/services/scheduling.py` `is_due` logic so the
tool description and spec stay accurate; if the worker uses a different
convention, the worker is authoritative — adjust this doc and the helper.

## Response Shaping

- **List**: trimmed summary per slot — `id`, `kind`, `status`,
  `target_date` or `day_of_week`+`end_date`, `start_time`, `end_time`,
  `num_slots`, `partners`, and the most recent attempt outcome (if any).
- **Get**: pass through the full `WantedResponse` (includes
  `has_credentials`, full `attempts`). `credentials` is already stripped
  server-side (`WantedResponse.from_slot`).
- **Create / update / set_enabled**: return the same trimmed summary as
  list, so the caller can confirm what was stored.

## Error Handling

Mirrors the existing tools:

- Local: `DateParseError` (bad date/time/day-of-week), invalid `status`,
  out-of-range numeric day → `{"error": str}` **before** any HTTP call.
- Remote: `ApiError` (401-after-retry, 404, 422, 5xx) → `{"error": str}`.
  The `ApiClient` already extracts the API's `detail` string.
- Validation the API already enforces (window ordering, `num_slots` 1–4,
  ≤3 partners, kind/date invariants) is **not** duplicated in the MCP —
  the 422 detail is surfaced back so the LLM can correct itself. Local
  pre-checks are limited to parse failures that save an obvious round-trip.

## Testing

Follow `mcp/tests/` patterns:

- Unit test per tool with a stubbed `ApiClient` — success path and at
  least one error path (parse error and/or API error) each.
- Day-of-week + date normalization unit tests (names, abbreviations,
  ints, numeric strings, invalid input).
- `credentials` auto-encryption asserted on the create tools (encrypted
  blob present in the request body, not a plaintext field).
- Update `test_tools.py` `list_tools()` smoke test to assert all 7 new
  tools register (11 total).

Run: `cd mcp && uv run pytest`.

## Documentation

Update `mcp/README.md` and the CLAUDE.md MCP section with the 7 new tools
(reference + the 0=Monday day-of-week convention).

## Out of Scope

- SMS `notify` on wanted slots via MCP (slots created via MCP never notify).
- Per-call credential override (always the configured account).
- Editing `kind` / `target_date` / `day_of_week` of an existing slot
  (immutable in the API; recreate instead).

## Workflow Note

Implementation will be done on a new git worktree taken from `main`
(per the originating request) and shipped as a single combined PR
(per project preference for multi-phase work).
