# Wanted Tee-Times Web UI — Design

**Status:** approved (brainstorming)
**Scope:** React SPA covering login + full CRUD over wanted tee-time requests.
Out of scope: live tee-time browse/book, partner management.

## Goals

A small single-page app that lets a logged-in user manage their persisted
auto-booking requests (`/api/wanted`): list them at a glance, create one-shot
or recurring slots, edit/disable/delete, and inspect attempt history.

## Non-goals

- Browsing or booking tee times directly.
- Managing partners (read-only consumption of `/api/partners` for the picker).
- Multi-user account features (this is a personal tool).
- End-to-end browser tests in this iteration.

## High-level architecture

```
                 ┌───────────────────────┐
 Browser (SPA) ──┤ nginx (charts/web)    │── /api/* ──▶ FastAPI (charts/api)
                 │ serves dist/ + /api ↗ │              ── Redis
                 └───────────────────────┘
```

- New package at `web/` (sibling to `api/`, `mcp/`) built with Vite +
  React + TypeScript + Tailwind + TanStack Query + React Router.
- New nginx Helm release `charts/tee-sniper-web` deployed alongside the API.
  Ingress routes `/api/*` to the API service and `/*` to the web service, so
  the browser issues same-origin relative requests and CORS is unneeded.
- One new backend endpoint (`POST /api/encrypt-credentials`) added to the
  existing FastAPI app so the browser never holds the AES shared secret.

## Repo layout

```
web/
  package.json, vite.config.ts, tsconfig.json, tailwind.config.ts
  src/
    main.tsx, App.tsx, router.tsx
    api/        # typed client + fetch wrapper + ApiError
    auth/       # AuthProvider, useAuth, ProtectedRoute
    crypto/     # thin wrapper around /api/encrypt-credentials
    pages/      { LoginPage, WantedListPage, WantedDetailPage, WantedNewPage }
    components/ { WantedCard, StatusPill, AttemptList,
                  RecurringForm, OneShotForm, NotifyFields,
                  PartnerPicker, ConfirmDialog }
    hooks/      { useWantedList, useWanted, useCreateWanted,
                  usePatchWanted, useDeleteWanted, useLogin, usePartners }
  test/         # vitest setup, MSW handlers
  Dockerfile    # multi-stage: node build → nginx:alpine serving dist/
  nginx.conf    # SPA fallback (try_files), runtime /config.js endpoint
  README.md

charts/tee-sniper-web/
  Chart.yaml, values.yaml
  templates/{deployment,service,ingress,configmap}.yaml

.github/workflows/web-build.yml   # lint + test + build + push GHCR image
```

## Backend change: `POST /api/encrypt-credentials`

Added to `api/app/routers/booking.py`. Auth-free (login can't precede it).

```python
class EncryptRequest(BaseModel):
    username: str
    pin: str

class EncryptResponse(BaseModel):
    credentials: str  # base64 AES-256-GCM blob

@router.post("/encrypt-credentials", response_model=EncryptResponse)
async def encrypt_credentials(
    body: EncryptRequest,
    encryption: EncryptionService = Depends(get_encryption_service),
) -> EncryptResponse:
    return EncryptResponse(
        credentials=encryption.encrypt_credentials(body.username, body.pin),
    )
```

Rationale for auth-free: the booking site itself validates `username:pin` on
the next `/api/login` call, so this endpoint is not a meaningful oracle — it
just encrypts arbitrary bytes with a key the server already controls. Tested
in `api/tests/test_booking_routes.py` with a roundtrip through
`EncryptionService.decrypt_credentials`.

## Auth & credential lifecycle (browser)

A single `AuthProvider` (React context) owns:

| State              | Persistence          | Notes                                      |
|--------------------|----------------------|--------------------------------------------|
| `token`            | sessionStorage       | Survives reload, dies with the tab.        |
| `username`         | sessionStorage       | For display only ("Logged in as …").       |
| `credentialsBlob`  | memory only          | Lost on reload; only needed for *create*.  |

**Login flow:**

1. User submits `{username, pin}` to `POST /api/encrypt-credentials`.
2. POST `/api/login` with the returned blob → `{access_token, expires_at}`.
3. Store token + username in state and sessionStorage, blob in memory only,
   redirect to `/wanted`.

**Authed fetch wrapper** attaches `Authorization: Bearer ${token}`. On any
`401` it clears auth state and redirects to `/login` — no silent refresh.

**Slot creation** attaches the in-memory blob to the POST body. If the blob
is absent (post-reload), the create form shows an inline "Re-enter PIN to
save" field that calls `/api/encrypt-credentials` again before submit.
Viewing, editing, disabling, and deleting existing slots never need the blob
(each slot already has its own stored credentials, and PATCH only sends the
new blob if `credentials` is explicitly being changed).

`ProtectedRoute` wraps `/wanted/*` and redirects to `/login` when there's no
token.

## Pages

### `/login`

Centered card: username, PIN, "Sign in". Errors surface inline:
- `401` → "Invalid username or PIN."
- `502` → "Booking site unreachable; try again shortly."
- network/other → "Something went wrong: <detail>."

### `/wanted` (list)

Card grid (`grid-cols-1 md:grid-cols-2 lg:grid-cols-3`). Each `WantedCard`
shows:

- Title — for one-shot: formatted target_date (e.g. "Sat 24 May"); for
  recurring: "Every \<Day\>".
- Time window, `num_slots`, partner count.
- `StatusPill` (pending / booked / expired / disabled).
- Last attempt summary ("2h ago · no_slots", "booked 09:42", or "No attempts
  yet").

Header: app name, "+ New" button, "Logged in as <username> · Logout".
Below the header, a chip row filters by status (All / Pending / Booked /
Disabled / Expired). Filter is purely client-side over the cached list.

`useWantedList` (`GET /api/wanted`):
- `refetchInterval: 60_000`
- `refetchOnWindowFocus: true`

Clicking a card navigates to `/wanted/:id`.

### `/wanted/new`

Segmented toggle at top: **One-shot** ↔ **Recurring**.

Common fields:
- `start_time`, `end_time` — `<input type="time">`, Zod-validated
  (`end_time > start_time`).
- `num_slots` — 1–4 (segmented control).
- Partners — `PartnerPicker` pulls from `GET /api/partners`, multi-select,
  max 3.
- Notify (optional) — `to` (E.164 input, validated), `from` (optional).

One-shot extra:
- `target_date` — date input, must satisfy `today ≤ d ≤ today + 7` (matches
  the 8-day booking window the worker enforces via
  `app/services/scheduling.py`). The client validates and the server is the
  source of truth.

Recurring extra:
- `day_of_week` — Mon–Sun chip group, single-select (stored as 0=Monday per
  the API).
- `end_date` — optional date input.

Submit → `POST /api/wanted?kind=one_shot|recurring` with the in-memory
credentials blob. Success → toast + `navigate('/wanted')`.

### `/wanted/:id`

Two-column layout (stacks on mobile):

**Left** — edit form pre-filled with the slot's current values. Only
PATCH-able fields are editable (per `PatchWantedRequest`): `start_time`,
`end_time`, `num_slots`, `partners`, `notify`. Buttons:
- **Save** — `PATCH /api/wanted/:id`.
- **Disable / Enable** — toggles via `{disabled: true|false}` in PATCH body.
- **Delete** — opens `ConfirmDialog`, then `DELETE /api/wanted/:id` →
  redirect to `/wanted`.

**Right** — `AttemptList`: newest-first list of `attempts[]` entries. Each
row shows timestamp, outcome pill, `booking_id` if booked, and `error` text
when present. Empty state: "No attempts yet."

## API client

`src/api/client.ts` — small hand-rolled `fetch` wrapper (~80 lines):

```ts
class ApiError extends Error {
  constructor(public status: number, public detail: string) { super(detail); }
}

async function request<T>(path: string, init?: RequestInit & { token?: string }): Promise<T>
```

Endpoint functions (typed): `login`, `encryptCredentials`, `listWanted`,
`getWanted`, `createWanted`, `patchWanted`, `deleteWanted`, `listPartners`.
Request/response types live in `src/api/types.ts` and are hand-mirrored from
`api/app/models/{wanted,requests,responses}.py`. No codegen; the surface is
small (~150 lines of types) and easy to keep in sync.

React Query keys: `['wanted']`, `['wanted', id]`, `['partners']`. Mutations
invalidate the relevant keys.

## Error handling

- Shared `<Toaster/>` (e.g. `sonner`) — one toast per `ApiError` from a
  mutation or non-list query.
- Form-level Zod errors render inline next to the field.
- `401` from anywhere triggers `auth.logout()` (clears state + redirect).
- `422` shows the FastAPI detail string inline above the form.

## Testing

- **Vitest + React Testing Library** for unit/component tests:
  `AuthProvider` flow, `WantedCard` rendering by status, attempt timeline,
  Zod form validation, partner picker constraints.
- **MSW** for HTTP mocking. Handlers in `web/test/handlers.ts` cover happy
  path + 401 + 422 + 502 for every endpoint.
- No Playwright/E2E in this iteration.
- CI: `web-build.yml` runs `npm ci && npm run lint && npm test &&
  npm run build`, then builds + pushes the GHCR image on `main`.

## Deployment

`web/Dockerfile`:

```Dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build           # → /app/dist

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```

`entrypoint.sh` writes `/usr/share/nginx/html/config.js` from the
`API_BASE_URL` env var (defaults to `""` → relative `/api`), enabling
per-environment configuration without rebuilding. `index.html` loads
`/config.js` before the bundle and the API client reads
`window.__TSA_CONFIG__.apiBaseUrl`.

`nginx.conf`:
- `try_files $uri /index.html;` for SPA routing.
- No `/api` proxy in the container — handled at the ingress.

`charts/tee-sniper-web/` mirrors `charts/tee-sniper-api`:
- `Deployment` — image + `API_BASE_URL` env (default `""`).
- `Service` — ClusterIP :80.
- `Ingress` — host + path-based routing (`/api/*` → api service, `/*` → web
  service).
- `ConfigMap` — anything else worth templating.

## Documentation

- `web/README.md` — dev (`npm install`, `npm run dev` proxying to API on
  `http://localhost:8000`), build, test, env vars, deployment notes.
- `CLAUDE.md` gains a "Web UI" section pointing at `web/` and listing the
  dev/test commands.

## Workflow

Per user preference for multi-phase plans: deliver as a **single PR** off a
worktree from `main`, sequenced internally but landing together. Branch
name: `web/wanted-ui`.

## Open questions

None at brainstorming time. Implementation-plan-level details (exact Zod
schemas, Tailwind theme choices, ingress path conventions) deferred to the
plan.
