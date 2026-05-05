# tee-sniper-mcp — Test Plan

Scope: validation strategy for the local MCP server in `mcp/`. Covers unit
tests, the cross-package roundtrip test, end-to-end smoke tests, and the
manual-verification checklist for changes that touch network or transport.

## Layers

```
┌────────────────────────────────────────────────────────────────────────┐
│ Manual / E2E    │ MCP client (Claude Desktop, MetaMCP) → live API     │
├────────────────────────────────────────────────────────────────────────┤
│ Smoke           │ uv run tee-sniper-mcp ↔ stdio (JSON-RPC)            │
├────────────────────────────────────────────────────────────────────────┤
│ Cross-package   │ encrypt locally → decrypt with api/EncryptionService │
├────────────────────────────────────────────────────────────────────────┤
│ Unit (mocked)   │ httpx mocked with respx; deterministic clock         │
└────────────────────────────────────────────────────────────────────────┘
```

The unit layer is the workhorse — every behavioural change must add or update
a test there. The other layers exist to catch what units cannot: transport
shape (smoke), cross-package contract drift (roundtrip), and real-world
integration (manual).

## Running the suite

```bash
# Default — fast, no network
cd mcp && uv run pytest -v

# With coverage (one-off; pytest-cov is not in deps by default)
cd mcp && uv run --with pytest-cov pytest --cov=tee_sniper_mcp --cov-report=term-missing
```

Targeted runs for a single module:

```bash
uv run --directory mcp pytest tests/test_dates.py -v
uv run --directory mcp pytest tests/test_tools.py::test_find_tee_times_with_band -v
```

Expected baseline: **46 passing, 0 failing, 0 skipped** (as of PR #71).

## Unit tests

Five test modules, one per source module. All HTTP is mocked at the transport
layer with `respx`; environment is mocked with pytest's `monkeypatch`; logs are
captured with `caplog`; filesystem with `tmp_path`. **No** test mocks internal
methods of the unit under test — they verify observable behaviour.

### `tests/test_config.py` — env loading

Covers `Config` and `load_config()` in `src/tee_sniper_mcp/config.py`.

| Test | What it asserts |
|---|---|
| `test_load_config_reads_required_env` | All four required env vars produce the expected `Config` dataclass. |
| `test_load_config_strips_trailing_slash` | `TSA_API_BASE_URL` trailing slash is normalised away. |
| `test_load_config_parses_time_bands_override` | Valid `TSA_TIME_BANDS` JSON populates `time_bands_override`. |
| `test_load_config_raises_when_missing_required` | Missing any required var → `ConfigError` listing the missing names. |
| `test_load_config_raises_on_invalid_time_bands_json` | Malformed `TSA_TIME_BANDS` → `ConfigError` mentioning the var name. |
| `test_config_repr_does_not_leak_secrets` | `repr(config)` does not contain `pin` or `shared_secret` values. |

### `tests/test_dates.py` — parsing

Covers `src/tee_sniper_mcp/dates.py`. Uses a fixed `today=Mon 2026-05-04` for
deterministic relative-date assertions.

| Test | What it asserts |
|---|---|
| `test_parse_date_iso` | ISO string → exact date. |
| `test_parse_date_today` | `"today"` → fixture date. |
| `test_parse_date_tomorrow` | Case-insensitive (`"Tomorrow"`). |
| `test_parse_date_in_n_days` | `"in 3 days"` → +3. |
| `test_parse_date_next_weekday` | `"next saturday"` → +5 from Monday. |
| `test_parse_date_this_weekday_future` | `"this friday"` → +4. |
| `test_parse_date_invalid_raises` | Garbage input → `DateParseError`. |
| `test_parse_time_*` (3 tests) | `"15:00"`, `"3pm"`, `"3:30 PM"` all → `"HH:MM"`. |
| `test_parse_time_invalid_raises` | Garbage input → `DateParseError`. |
| `test_resolve_band_default` | `early_morning` resolves to documented range. |
| `test_resolve_band_all_day_returns_none` | `all_day` → `(None, None)` (no filter). |
| `test_resolve_band_unknown_raises` | Unknown name → `DateParseError`. |
| `test_resolve_band_with_override` | `TSA_TIME_BANDS` override values are used. |
| `test_resolve_window_*` (3 tests) | Explicit times beat band; band used otherwise; both absent → no filter. |

### `tests/test_auth.py` — credentials, login lifecycle

Covers `src/tee_sniper_mcp/auth.py`. Uses `respx` for `/api/login` mocking.

| Test | What it asserts |
|---|---|
| `test_encrypt_credentials_roundtrip` | Locally-encrypted blob decrypts cleanly with `api/`'s `EncryptionService`. **Cross-package** — see below. |
| `test_get_token_calls_login_once_then_caches` | First call hits `/api/login`; second returns cached token without a network call. |
| `test_invalidate_forces_relogin` | `auth.invalidate()` clears state; next `get_token()` re-logs-in and returns a fresh token. |
| `test_login_failure_raises` | 401 from `/api/login` → `AuthError` carrying the API's `detail`. |
| `test_unexpected_login_body_raises_auth_error` | 200 with malformed JSON (missing `access_token`) → `AuthError`, not raw `KeyError`. |

### `tests/test_api_client.py` — HTTP wrapper, retry semantics

Covers `src/tee_sniper_mcp/api_client.py`. Mocks both `/api/login` and a
representative endpoint; asserts on the request the wrapper sent.

| Test | What it asserts |
|---|---|
| `test_get_attaches_bearer_token` | Outgoing request has `Authorization: Bearer <token>`. |
| `test_401_triggers_one_retry` | Single 401 → `auth.invalidate()` → second login → retried call returns 200. Login mock called twice; endpoint called twice. |
| `test_persistent_401_raises` | Two consecutive 401s → `ApiError` (does not retry forever). |
| `test_non_401_error_surfaces` | 502 surfaces as `ApiError` carrying the API `detail`. |
| `test_list_body_error_does_not_crash` | Error response with a JSON list body (e.g. FastAPI 422) does not raise `AttributeError`. |
| `test_post_passes_json_body` | Outgoing POST body matches the exact JSON the caller passed. |

### `tests/test_tools.py` — tool surface

Covers `src/tee_sniper_mcp/tools.py` and `src/tee_sniper_mcp/server.py`.

The `tools` fixture wraps each test in a respx `MockRouter` with login mocked
upfront. Individual tests register the per-endpoint mocks they need via the
`@respx.mock` decorator.

| Test | What it asserts |
|---|---|
| `test_find_tee_times_with_band` | `time_of_day="early_morning"` → `start=06:00&end=09:00` query params; result contains only `time` and `can_book` (no `booking_form`). |
| `test_find_tee_times_explicit_times_override_band` | When both explicit times and band are supplied, explicit wins. |
| `test_find_tee_times_invalid_date_returns_error` | Garbage date → `{"error": "..."}`, no exception. |
| `test_find_tee_times_handles_malformed_api_response` | API returns 200 with `{}` → `{"error": "unexpected API response: ..."}`, no `KeyError`. |
| `test_book_tee_time_passes_through` | Date/time parsing + JSON body shape + `slots_booked` → `num_slots` rename in the result. |
| `test_book_tee_time_handles_malformed_api_response` | Same malformed-body guard for the book path. |
| `test_list_partners_normalises_response` | `/api/partners` response passed through unchanged. |
| `test_add_partners_passes_through` | PATCH path, JSON body, return shape all correct. |
| `test_add_partners_handles_malformed_api_response` | Same malformed-body guard for the add-partners path. |
| `test_api_error_surfaces_as_error_dict` | Upstream 502 → `{"error": "..."}`, not raised. |
| `test_server_registers_all_four_tools` | `build_server` registers exactly `find_tee_times`, `book_tee_time`, `list_partners`, `add_partners`. Smoke test for the FastMCP wiring. |

## Cross-package roundtrip test

`tests/test_auth.py::test_encrypt_credentials_roundtrip` is the **only** test
that imports from `api/`. It guards against the local AES-GCM implementation
in `mcp/src/tee_sniper_mcp/auth.py` drifting away from the API's
`app.services.encryption.EncryptionService`.

How it's wired:

- `mcp/conftest.py` adds `../api` to `sys.path` if it exists.
- The test imports `from app.services.encryption import EncryptionService` and
  decrypts what `encrypt_credentials` produced, asserting the original
  username/pin pair comes back.

Operational note: importing `app.services.encryption` cascades through
`app/services/__init__.py`, which re-exports from `session_manager.py`. That
module imports `redis`, which is why `redis` is in `mcp/pyproject.toml`'s dev
dep group. **Removing it breaks this test** — the comment in `pyproject.toml`
explains.

If the API's `EncryptionService` changes (key derivation, nonce size, AAD,
output format), this test fails first and tells us to update `auth.py` in
lockstep.

## End-to-end smoke test

Uses the actual stdio entrypoint against a running API. **Not run in CI**
(needs live credentials and a running FastAPI). Run before merging changes
that touch transport, auth, or any tool's request shape.

```bash
# Terminal 1 — start the API
cd api && .venv/bin/uvicorn app.main:app --reload

# Terminal 2 — drive the MCP server via JSON-RPC
cd mcp
TSA_API_BASE_URL=http://localhost:8000 \
TSA_USERNAME=… TSA_PIN=… TSA_SHARED_SECRET=… \
uv run tee-sniper-mcp <<EOF
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
EOF
```

Expect:

1. The `initialize` response advertises tools.
2. The `tools/list` response contains the four tool names (`find_tee_times`,
   `book_tee_time`, `list_partners`, `add_partners`) with the documented
   parameter schemas.
3. No login is performed yet — only on the first tool call that needs it.

To exercise an actual tool call (use `dry_run` so nothing books):

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call",
 "params":{"name":"find_tee_times","arguments":{"date":"tomorrow","time_of_day":"morning"}}}
```

## CI

`.github/workflows/mcp-build.yml` runs on any push or PR that touches
`mcp/**` or the workflow file itself.

| Job | Steps |
|---|---|
| `test` | checkout → Python 3.14 → `astral-sh/setup-uv@v3` → `uv sync --all-extras --dev` → `uv run pytest -v` |
| `build` (needs test) | Docker buildx → build `mcp/Dockerfile` (no push) with GHA cache. |

The `build` job is the only validation we currently have for the Dockerfile —
local Docker is optional, so any breakage shows up here.

`.github/workflows/release.yml` additionally builds and pushes
`ghcr.io/<repo>-mcp` on tag push (`v*.*.*`). That image build also acts as a
release-time integrity check.

## Manual verification checklist (Claude Desktop / MetaMCP)

Use after any change to `server.py`, tool descriptions, or transport behaviour.

- [ ] Wire the server into Claude Desktop using the snippet in
      `mcp/README.md`. Verify the four tools appear in the tool picker.
- [ ] Ask Claude: *"Find me a tee time tomorrow morning."* Confirm
      `find_tee_times` is called with `date="tomorrow"` and either
      `time_of_day="morning"` or appropriate explicit times.
- [ ] Ask Claude: *"Book the 09:00 slot tomorrow as a dry run."* Confirm
      `book_tee_time` is called with `dry_run=true` and a `booking_id` is
      returned.
- [ ] Ask Claude: *"List my saved partners."* Confirm `list_partners` returns
      the contents of `TSA_PARTNERS_FILE`.
- [ ] Ask Claude: *"Add Alice and Bob to that booking (dry run)."* Confirm
      `add_partners` is called with `partner_ids=[…]` and `dry_run=true`.
- [ ] Repeat the booking flow without restarting the MCP server. Confirm only
      one `/api/login` call is made (check API logs).
- [ ] Restart the API and trigger a tool call. Confirm the MCP server
      transparently re-logs-in on the resulting 401.
- [ ] If using MetaMCP: confirm the server stays alive across multiple
      sessions (no per-call respawn).

## What is intentionally out of scope

- **Live booking tests in CI.** Booking touches a real golf-course site and
  cannot be exercised safely from CI. Smoke tests with `dry_run=true` are
  the substitute.
- **PyPI / `uvx` publication tests.** The release pipeline publishes Docker
  only; no PyPI artefact yet.
- **Concurrent-session tests.** A single MCP server process serves one user;
  no concurrency primitives beyond the `asyncio.Lock` around login.
- **Schema fuzzing of FastMCP descriptions.** The smoke test confirms tool
  *names* are registered; the *descriptions* are reviewed by hand.

## When tests fail

- **Roundtrip test fails:** `api/EncryptionService` and our `encrypt_credentials`
  have drifted. Re-read both files, align them, and update the comment in
  `auth.py` if needed.
- **`list_tools()` smoke test fails after a FastMCP upgrade:** the
  introspection API may have moved. Update the test to whichever helper the
  new version exposes (`get_tools()`, `_tool_manager`, etc.) and note the
  version bump in `mcp/pyproject.toml`.
- **A respx test starts intermittently failing:** check that the test using
  the `tools` fixture is still wrapped with `@respx.mock`. The fixture's
  `MockRouter` uses `assert_all_called=False` to avoid spurious failures
  from short-circuiting tests, but ad-hoc mocks added to the global respx
  router still need a decorator.
