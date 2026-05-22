# Manual Test Plan — Wanted Tee-Times Web UI

## Preconditions / setup

1. **Backend running** on `http://localhost:8000`:
   - Redis reachable; `TSA_SHARED_SECRET` set; `TSA_PARTNERS_FILE` pointing at a
     JSON `{id: name}` map (needed for the partner picker to be non-empty).
   - Booking-site `base_url` configured.
2. **Frontend**: `cd web && npm install && npm run dev` → open
   `http://localhost:5173` (Vite proxies `/api` → `:8000`).
3. Have **valid booking-site credentials** (member username + PIN) and at least
   one **invalid** PIN for negative tests.

---

## A. Authentication

| # | Steps | Expected |
|---|-------|----------|
| A1 | Visit `/wanted` (or any protected route) while logged out | Redirected to `/login` |
| A2 | Submit empty username and/or PIN | Inline "Username required" / "PIN required"; no network call |
| A3 | Log in with **valid** credentials | Lands on `/wanted`; header shows "Logged in as `<username>`" |
| A4 | Log in with **invalid** PIN | Error "Invalid username or PIN." shown; stays on `/login` |
| A5 | Stop the API, attempt login | Error "Booking site unreachable; try again shortly." (502) or a generic error if connection refused |
| A6 | After A3, open DevTools → Application → Session Storage | `tsa.token`, `tsa.username`, `tsa.expiresAt` present; **no** `tsa.credentialsBlob` (blob is memory-only) |
| A7 | After A3, reload the page | Still logged in (token persisted); list loads |
| A8 | Click **Logout** | Returns to `/login`; sessionStorage `tsa.*` cleared |

---

## B. List page (`/wanted`)

| # | Steps | Expected |
|---|-------|----------|
| B1 | Land on list with ≥1 slot | Card grid; each card shows title, time window, slots, partner count, status pill, last-attempt summary |
| B2 | One-shot slot card | Title is the formatted date (e.g. "Sat 24 May") |
| B3 | Recurring slot card | Title is "Every `<Day>`" |
| B4 | Slot with no attempts | Shows "No attempts yet" |
| B5 | Click filter chips (All / Pending / Booked / Disabled / Expired) | Grid filters client-side; only matching statuses show |
| B6 | A `disabled` slot | Card appears dimmed (reduced opacity) |
| B7 | Click a card | Navigates to `/wanted/:id` |
| B8 | Leave the tab and return (window focus), or wait ~60s | List silently refetches (attempt history/status updates without manual reload) |
| B9 | Empty/filtered-empty state | "No wanted slots match this filter." |

---

## C. Create — one-shot (`/wanted/new`)

| # | Steps | Expected |
|---|-------|----------|
| C1 | Click "+ New" | Lands on `/wanted/new`, "One-shot" tab active |
| C2 | Set end time ≤ start time, submit | Inline "End time must be after start time"; no submit |
| C3 | Try a target date in the past or > 8 days out | Date input min=today, max=today+7 prevents/flags it |
| C4 | Select 4th partner after 3 chosen | 4th checkbox disabled (cap of 3); already-checked boxes still uncheckable |
| C5 | Enter a malformed notify "To" (not E.164) | Inline E.164 error; leaving notify blank is allowed (no error) |
| C6 | Valid form → submit | Success toast "Wanted slot created"; navigates to `/wanted`; new card appears |
| C7 | Inspect the create request (Network tab) | `POST /api/wanted?kind=one_shot`; body includes `credentials` (the blob), `target_date`, times, `num_slots`, `partners` |

---

## D. Create — recurring

| # | Steps | Expected |
|---|-------|----------|
| D1 | Switch to "Recurring" tab | Day-of-week selector + optional end-date appear; target-date field gone |
| D2 | Pick a day, valid window, submit | `POST /api/wanted?kind=recurring` with `day_of_week` (Mon=0…Sun=6); success toast + redirect |
| D3 | Verify the day mapping | Selecting "Mon" sends `day_of_week: 0`; recurring card shows "Every Monday" |

---

## E. Credentials re-prompt (memory-only blob)

| # | Steps | Expected |
|---|-------|----------|
| E1 | Log in, go to `/wanted/new` **without reloading** | No PIN prompt (in-memory blob reused); create works directly |
| E2 | Reload the page, then go to `/wanted/new` | Amber "Re-enter your PIN to save credentials" prompt appears |
| E3 | Submit with the PIN field filled | Re-encrypts via `/api/encrypt-credentials`, then creates the slot successfully |
| E4 | Submit with PIN left blank (after reload) | Error toast "Re-enter PIN to save"; no slot created |

---

## F. Detail / edit (`/wanted/:id`)

| # | Steps | Expected |
|---|-------|----------|
| F1 | Open a slot | Left: edit form pre-filled with current start/end/slots; right: attempt timeline; status pill shown |
| F2 | Change times/slots → **Save** | `PATCH /api/wanted/:id`; "Saved" toast; values persist after reload |
| F3 | Click **Disable** on a pending slot | Status → disabled (`{disabled:true}`); button now reads "Enable" |
| F4 | Click **Enable** on a disabled slot | Status → pending |
| F5 | Click **Delete** | ConfirmDialog "Delete this wanted slot?" appears |
| F6 | Cancel the dialog | No deletion; stays on page |
| F7 | Confirm deletion | `DELETE /api/wanted/:id`; "Deleted" toast; navigates to `/wanted`; card gone |
| F8 | Slot with attempts | Timeline lists newest-first: timestamp, outcome, booking_id (if booked), error text (if failed) |
| F9 | Save with an invalid window (end ≤ start) | Backend 422 surfaces as an error toast |

---

## G. Routing & errors

| # | Steps | Expected |
|---|-------|----------|
| G1 | Visit an unknown path (e.g. `/foo`) | Redirects to `/wanted` (catch-all) |
| G2 | Deep-link `/wanted/:id` while logged out | Redirected to `/login` |
| G3 | Let the session expire / delete `tsa.token`, then trigger an API call | 401 → auth cleared → redirect to `/login` |
| G4 | Network failure on the list | "Failed to load wanted slots." message |

---

## H. Deployment smoke (optional, needs Docker/k8s)

| # | Steps | Expected |
|---|-------|----------|
| H1 | `docker build -t web web/` then run with `-e API_BASE_URL=https://host/api` | Container serves on :80 |
| H2 | `GET /config.js` | Returns `window.__TSA_CONFIG__ = { apiBaseUrl: "https://host/api" };` |
| H3 | Default (no `API_BASE_URL`) | `config.js` has `apiBaseUrl: ""` → app uses relative `/api/*` |
| H4 | Refresh on a deep route (e.g. `/wanted/abc`) in the container | nginx `try_files` serves `index.html` (no 404) |
| H5 | `helm template charts/tee-sniper-web` | Renders Deployment + Service + Ingress; ingress splits `/api` → API service, `/` → web |
