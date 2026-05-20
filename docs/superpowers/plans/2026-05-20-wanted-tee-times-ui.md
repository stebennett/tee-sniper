# Wanted Tee-Times Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a React SPA at `web/` covering login + full CRUD over wanted tee-time requests, served behind nginx via a new Helm chart, plus the one backend endpoint that lets the browser produce encrypted credentials.

**Architecture:** New top-level package `web/` (Vite + React + TypeScript + Tailwind + TanStack Query + React Router + Zod + Vitest + MSW). All API calls go through a single typed fetch wrapper; auth state lives in a React context (token in sessionStorage, encrypted-credentials blob in memory only). One new FastAPI endpoint `POST /api/encrypt-credentials` lets the browser request encryption without holding the shared secret. Deployment: a multi-stage Docker image (node build → `nginx:alpine` serving `dist/`) deployed via a new `charts/tee-sniper-web` chart; ingress routes `/api/*` to the API service and `/*` to the web service, so the browser uses relative URLs and CORS is unneeded.

**Tech Stack:** React 18, TypeScript 5, Vite 5, Tailwind CSS 3, TanStack Query v5, React Router v6, Zod 3, react-hook-form, sonner (toasts), Vitest, @testing-library/react, MSW v2, nginx:alpine.

**Workflow:** Per the user's preference, deliver as a **single combined PR** off a worktree from `main`, branch `web/wanted-ui`. Subagent implementers commit locally; the controller handles push/PR.

**Spec:** `docs/superpowers/specs/2026-05-20-wanted-tee-times-ui-design.md`.

---

## File map

**Created**
- `web/package.json`, `web/package-lock.json`
- `web/vite.config.ts`, `web/tsconfig.json`, `web/tsconfig.node.json`
- `web/tailwind.config.ts`, `web/postcss.config.js`
- `web/.eslintrc.cjs`, `web/.gitignore`
- `web/index.html`
- `web/src/main.tsx`, `web/src/App.tsx`, `web/src/router.tsx`, `web/src/index.css`
- `web/src/config.ts`
- `web/src/api/types.ts`, `web/src/api/client.ts`, `web/src/api/endpoints.ts`
- `web/src/auth/AuthProvider.tsx`, `web/src/auth/useAuth.ts`, `web/src/auth/ProtectedRoute.tsx`
- `web/src/crypto/encrypt.ts`
- `web/src/hooks/useWanted.ts`, `web/src/hooks/usePartners.ts`, `web/src/hooks/useLogin.ts`
- `web/src/pages/LoginPage.tsx`, `web/src/pages/WantedListPage.tsx`, `web/src/pages/WantedNewPage.tsx`, `web/src/pages/WantedDetailPage.tsx`
- `web/src/components/{StatusPill,WantedCard,ConfirmDialog,NotifyFields,PartnerPicker,AttemptList,OneShotForm,RecurringForm,SlotFormFields}.tsx`
- `web/src/lib/format.ts`, `web/src/lib/schemas.ts`
- `web/test/setup.ts`, `web/test/handlers.ts`, `web/test/utils.tsx`
- `web/src/**/*.test.ts(x)` — co-located component/unit tests
- `web/Dockerfile`, `web/nginx.conf`, `web/entrypoint.sh`, `web/README.md`
- `charts/tee-sniper-web/Chart.yaml`, `charts/tee-sniper-web/values.yaml`
- `charts/tee-sniper-web/templates/{deployment,service,ingress,configmap,_helpers.tpl}.yaml`
- `.github/workflows/web-build.yml`
- `api/app/models/requests.py` — add `EncryptRequest`
- `api/app/models/responses.py` — add `EncryptResponse`
- `api/tests/test_booking_routes.py` — add encrypt-credentials roundtrip test

**Modified**
- `api/app/routers/booking.py` — add `POST /api/encrypt-credentials`
- `CLAUDE.md` — add "Web UI" section
- `.gitignore` — add `web/node_modules`, `web/dist`, `.superpowers/`

---

## Task 0: Worktree + branch

**Files:**
- (none)

- [ ] **Step 1: Create the worktree from main**

```bash
cd /Users/stevebennett/Code/tee-sniper
git fetch origin
git worktree add -b web/wanted-ui ../tee-sniper-web-ui origin/main
cd ../tee-sniper-web-ui
```

All subsequent tasks assume `cwd = /Users/stevebennett/Code/tee-sniper-web-ui` and branch `web/wanted-ui`.

- [ ] **Step 2: Sanity check**

```bash
git status
git log --oneline -1
```

Expected: clean tree, HEAD matches `origin/main`.

---

## Task 1: Backend — `POST /api/encrypt-credentials`

**Files:**
- Modify: `api/app/models/requests.py`
- Modify: `api/app/models/responses.py`
- Modify: `api/app/routers/booking.py`
- Test: `api/tests/test_booking_routes.py`

- [ ] **Step 1: Add the failing test**

Append to `api/tests/test_booking_routes.py`:

```python
def test_encrypt_credentials_roundtrip(client, encryption_service):
    """POST /api/encrypt-credentials returns a blob the server can decrypt."""
    resp = client.post(
        "/api/encrypt-credentials",
        json={"username": "alice", "pin": "1234"},
    )
    assert resp.status_code == 200
    blob = resp.json()["credentials"]
    assert isinstance(blob, str) and len(blob) > 0

    username, pin = encryption_service.decrypt_credentials(blob)
    assert (username, pin) == ("alice", "1234")


def test_encrypt_credentials_validation():
    """Missing fields → 422."""
    from fastapi.testclient import TestClient
    from app.main import app
    resp = TestClient(app).post("/api/encrypt-credentials", json={"username": "x"})
    assert resp.status_code == 422
```

If `encryption_service` fixture does not yet exist, add to `api/tests/conftest.py`:

```python
import pytest
from app.services.encryption import EncryptionService
from app.config import get_settings

@pytest.fixture
def encryption_service() -> EncryptionService:
    return EncryptionService(get_settings().shared_secret)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd api && .venv/bin/python -m pytest tests/test_booking_routes.py::test_encrypt_credentials_roundtrip -v
```

Expected: FAIL — 404 on the endpoint.

- [ ] **Step 3: Add `EncryptRequest` to `api/app/models/requests.py`**

Append at end:

```python
class EncryptRequest(BaseModel):
    """Plaintext credentials for server-side encryption."""

    username: str = Field(..., min_length=1)
    pin: str = Field(..., min_length=1)
```

- [ ] **Step 4: Add `EncryptResponse` to `api/app/models/responses.py`**

Append at end:

```python
class EncryptResponse(BaseModel):
    """Encrypted credentials blob produced by /api/encrypt-credentials."""

    credentials: str = Field(
        ...,
        description="AES-256-GCM encrypted 'username:pin', base64 encoded",
    )
```

- [ ] **Step 5: Add the route in `api/app/routers/booking.py`**

Add to the imports near the top (extend the existing ones):

```python
from app.models.requests import (
    AddPartnersRequest,
    BookRequest,
    EncryptRequest,
    LoginRequest,
)
from app.models.responses import (
    # ...existing names...
    EncryptResponse,
)
```

Append a new route below `login`:

```python
@router.post(
    "/encrypt-credentials",
    response_model=EncryptResponse,
    status_code=status.HTTP_200_OK,
    responses={
        422: {"model": ErrorResponse, "description": "Invalid request body"},
    },
    summary="Encrypt credentials with the server's shared secret",
)
async def encrypt_credentials(
    body: EncryptRequest,
    encryption: EncryptionService = Depends(get_encryption_service),
) -> EncryptResponse:
    """Encrypt 'username:pin' for use in /api/login and wanted-slot storage.

    Auth-free: login cannot precede this call, and the booking site itself
    validates whether the credentials are real on the subsequent /api/login.
    """
    return EncryptResponse(
        credentials=encryption.encrypt_credentials(body.username, body.pin),
    )
```

- [ ] **Step 6: Run both tests, verify pass**

```bash
cd api && .venv/bin/python -m pytest tests/test_booking_routes.py -v -k encrypt
```

Expected: 2 passed.

- [ ] **Step 7: Run the full api suite as a regression check**

```bash
cd api && .venv/bin/python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add api/app/models/requests.py api/app/models/responses.py \
        api/app/routers/booking.py api/tests/test_booking_routes.py \
        api/tests/conftest.py
git commit -m "feat(api): add POST /api/encrypt-credentials"
```

---

## Task 2: Scaffold the `web/` package

**Files:**
- Create: `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/tsconfig.node.json`, `web/tailwind.config.ts`, `web/postcss.config.js`, `web/.eslintrc.cjs`, `web/.gitignore`, `web/index.html`, `web/src/main.tsx`, `web/src/App.tsx`, `web/src/index.css`, `web/src/vite-env.d.ts`
- Modify: `.gitignore`

- [ ] **Step 1: Create `web/package.json`**

```json
{
  "name": "tee-sniper-web",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.51.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-hook-form": "^7.52.0",
    "react-router-dom": "^6.26.0",
    "sonner": "^1.5.0",
    "zod": "^3.23.0",
    "@hookform/resolvers": "^3.9.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.6",
    "@testing-library/react": "^16.0.0",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@typescript-eslint/eslint-plugin": "^7.16.0",
    "@typescript-eslint/parser": "^7.16.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.19",
    "eslint": "^8.57.0",
    "eslint-plugin-react-hooks": "^4.6.2",
    "eslint-plugin-react-refresh": "^0.4.7",
    "jsdom": "^24.1.0",
    "msw": "^2.3.0",
    "postcss": "^8.4.39",
    "tailwindcss": "^3.4.6",
    "typescript": "^5.5.0",
    "vite": "^5.3.0",
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 2: Create `web/vite.config.ts`**

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./test/setup.ts'],
    globals: true,
    css: false,
  },
});
```

- [ ] **Step 3: Create `web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "esModuleInterop": true,
    "resolveJsonModule": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "test"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 4: Create `web/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 5: Create `web/tailwind.config.ts`**

```ts
import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: { extend: {} },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 6: Create `web/postcss.config.js`**

```js
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
```

- [ ] **Step 7: Create `web/.eslintrc.cjs`**

```js
module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', '.eslintrc.cjs'],
  parser: '@typescript-eslint/parser',
  plugins: ['react-refresh'],
  rules: {
    'react-refresh/only-export-components': 'warn',
  },
};
```

- [ ] **Step 8: Create `web/.gitignore`**

```
node_modules
dist
coverage
.env.local
```

- [ ] **Step 9: Create `web/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Tee Sniper</title>
    <script src="/config.js"></script>
  </head>
  <body class="bg-slate-950 text-slate-100">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 10: Create `web/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 11: Create `web/src/vite-env.d.ts`**

```ts
/// <reference types="vite/client" />

declare global {
  interface Window {
    __TSA_CONFIG__?: { apiBaseUrl?: string };
  }
}

export {};
```

- [ ] **Step 12: Create `web/src/main.tsx`**

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 13: Create placeholder `web/src/App.tsx`**

```tsx
export function App() {
  return <div className="p-8">Tee Sniper — bootstrapping…</div>;
}
```

- [ ] **Step 14: Update root `.gitignore`**

Append:

```
.superpowers/
```

(Already covered by `web/.gitignore`, but `.superpowers/` is the brainstorm dir.)

- [ ] **Step 15: Install dependencies and run a build smoke test**

```bash
cd web && npm install
npm run build
```

Expected: clean install (no peer-dep errors that fail the install), `dist/` produced.

- [ ] **Step 16: Commit**

```bash
git add web/ .gitignore
git commit -m "chore(web): scaffold Vite + React + TS + Tailwind"
```

---

## Task 3: Test infrastructure (Vitest + MSW)

**Files:**
- Create: `web/test/setup.ts`, `web/test/handlers.ts`, `web/test/utils.tsx`

- [ ] **Step 1: Create `web/test/setup.ts`**

```ts
import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { server } from './handlers';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

- [ ] **Step 2: Create `web/test/handlers.ts`**

```ts
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

export const baseUrl = 'http://api.test';

// Default happy-path handlers. Individual tests override per-case.
export const handlers = [
  http.post(`${baseUrl}/api/encrypt-credentials`, async ({ request }) => {
    const body = (await request.json()) as { username: string; pin: string };
    return HttpResponse.json({ credentials: `enc(${body.username}:${body.pin})` });
  }),
  http.post(`${baseUrl}/api/login`, () =>
    HttpResponse.json({
      access_token: 'test-token',
      expires_at: new Date(Date.now() + 3600_000).toISOString(),
    }),
  ),
  http.get(`${baseUrl}/api/wanted`, () => HttpResponse.json([])),
  http.get(`${baseUrl}/api/partners`, () => HttpResponse.json({ partners: [] })),
];

export const server = setupServer(...handlers);
```

- [ ] **Step 3: Create `web/test/utils.tsx`**

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '../src/auth/AuthProvider';

export function renderWithProviders(
  ui: ReactElement,
  { route = '/', initialAuth }: { route?: string; initialAuth?: Parameters<typeof AuthProvider>[0]['initial'] } = {},
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <AuthProvider initial={initialAuth}>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
```

`AuthProvider` is defined in Task 5. This file will not type-check yet — that's fine; first real test that imports `renderWithProviders` arrives in Task 5.

- [ ] **Step 4: Smoke-test vitest startup**

```bash
cd web && npx vitest run --reporter verbose
```

Expected: "No test files found." (or "0 passed") with no setup errors.

- [ ] **Step 5: Commit**

```bash
git add web/test/
git commit -m "test(web): add vitest setup + MSW handlers"
```

---

## Task 4: API types + client

**Files:**
- Create: `web/src/api/types.ts`, `web/src/api/client.ts`, `web/src/api/endpoints.ts`, `web/src/config.ts`
- Test: `web/src/api/client.test.ts`, `web/src/api/endpoints.test.ts`

- [ ] **Step 1: Create `web/src/config.ts`**

```ts
export function apiBaseUrl(): string {
  // Runtime override via /config.js → window.__TSA_CONFIG__.
  // Tests inject http://api.test via vitest globals.
  if (typeof window !== 'undefined' && window.__TSA_CONFIG__?.apiBaseUrl !== undefined) {
    return window.__TSA_CONFIG__.apiBaseUrl;
  }
  return '';
}
```

- [ ] **Step 2: Create `web/src/api/types.ts`**

Hand-mirrored from `api/app/models/wanted.py` + `requests.py` + `responses.py`:

```ts
export type WantedKind = 'one_shot' | 'recurring';
export type WantedStatus = 'pending' | 'booked' | 'expired' | 'disabled';
export type Outcome =
  | 'booked' | 'no_slots' | 'auth_failed' | 'upstream_error' | 'booking_failed';

export interface Notify { to: string; from?: string }

export interface Attempt {
  ts: string;
  target_date: string;
  outcome: Outcome;
  booking_id?: string | null;
  error?: string | null;
}

export interface WantedResponse {
  id: string;
  kind: WantedKind;
  target_date: string | null;
  day_of_week: number | null;
  end_date: string | null;
  start_time: string;
  end_time: string;
  num_slots: number;
  partners: string[];
  has_credentials: boolean;
  notify: Notify | null;
  status: WantedStatus;
  attempts: Attempt[];
  created_at: string;
  updated_at: string;
}

export interface LoginRequest { credentials: string }
export interface LoginResponse { access_token: string; expires_at: string }

export interface EncryptRequest { username: string; pin: string }
export interface EncryptResponse { credentials: string }

export interface CreateOneShotRequest {
  target_date: string;          // YYYY-MM-DD
  start_time: string;           // HH:MM
  end_time: string;             // HH:MM
  num_slots: number;
  partners: string[];
  credentials: string;
  notify?: Notify | null;
}

export interface CreateRecurringRequest {
  day_of_week: number;          // 0=Mon ... 6=Sun (matches Python weekday())
  end_date?: string | null;
  start_time: string;
  end_time: string;
  num_slots: number;
  partners: string[];
  credentials: string;
  notify?: Notify | null;
}

export interface PatchWantedRequest {
  start_time?: string;
  end_time?: string;
  num_slots?: number;
  partners?: string[];
  notify?: Notify | null;
  disabled?: boolean;
  credentials?: string;
}

export interface Partner { id: string; name: string }
export interface PartnerListResponse { partners: Partner[] }
```

- [ ] **Step 3: Write failing tests for `client.ts`**

`web/src/api/client.test.ts`:

```ts
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server, baseUrl } from '../../test/handlers';
import { ApiError, request } from './client';

// Force apiBaseUrl() to return baseUrl during tests.
beforeAll(() => {
  window.__TSA_CONFIG__ = { apiBaseUrl: baseUrl };
});

describe('request', () => {
  it('returns parsed JSON on 2xx', async () => {
    server.use(http.get(`${baseUrl}/ok`, () => HttpResponse.json({ hello: 'world' })));
    await expect(request<{ hello: string }>('/ok')).resolves.toEqual({ hello: 'world' });
  });

  it('throws ApiError with detail on non-2xx', async () => {
    server.use(
      http.get(`${baseUrl}/bad`, () =>
        HttpResponse.json({ detail: 'nope' }, { status: 422 }),
      ),
    );
    await expect(request('/bad')).rejects.toBeInstanceOf(ApiError);
    await expect(request('/bad')).rejects.toMatchObject({ status: 422, detail: 'nope' });
  });

  it('attaches Bearer token when provided', async () => {
    let seenAuth: string | null = null;
    server.use(
      http.get(`${baseUrl}/auth`, ({ request }) => {
        seenAuth = request.headers.get('authorization');
        return HttpResponse.json({});
      }),
    );
    await request('/auth', { token: 'abc' });
    expect(seenAuth).toBe('Bearer abc');
  });

  it('returns undefined for 204 No Content', async () => {
    server.use(http.delete(`${baseUrl}/x`, () => new HttpResponse(null, { status: 204 })));
    await expect(request('/x', { method: 'DELETE' })).resolves.toBeUndefined();
  });
});
```

- [ ] **Step 4: Run, expect failure**

```bash
cd web && npm test -- src/api/client.test.ts
```

Expected: FAIL — `client.ts` does not exist.

- [ ] **Step 5: Create `web/src/api/client.ts`**

```ts
import { apiBaseUrl } from '../config';

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail || `HTTP ${status}`);
    this.name = 'ApiError';
  }
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  token?: string | null;
}

export async function request<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { token, body, headers, ...rest } = opts;
  const init: RequestInit = {
    ...rest,
    headers: {
      Accept: 'application/json',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(headers as Record<string, string> | undefined),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  const resp = await fetch(`${apiBaseUrl()}${path}`, init);

  if (resp.status === 204) return undefined as T;

  const text = await resp.text();
  const data = text ? safeParse(text) : null;

  if (!resp.ok) {
    const detail = typeof data === 'object' && data && 'detail' in data
      ? String((data as { detail: unknown }).detail)
      : text || resp.statusText;
    throw new ApiError(resp.status, detail);
  }
  return data as T;
}

function safeParse(text: string): unknown {
  try { return JSON.parse(text); } catch { return text; }
}
```

- [ ] **Step 6: Run client tests, verify pass**

```bash
cd web && npm test -- src/api/client.test.ts
```

Expected: 4 passed.

- [ ] **Step 7: Write failing tests for `endpoints.ts`**

`web/src/api/endpoints.test.ts`:

```ts
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server, baseUrl } from '../../test/handlers';
import * as api from './endpoints';

beforeAll(() => { window.__TSA_CONFIG__ = { apiBaseUrl: baseUrl }; });

describe('endpoints', () => {
  it('encryptCredentials posts plaintext', async () => {
    const result = await api.encryptCredentials({ username: 'u', pin: 'p' });
    expect(result.credentials).toBe('enc(u:p)');
  });

  it('login posts the blob', async () => {
    const result = await api.login({ credentials: 'BLOB' });
    expect(result.access_token).toBe('test-token');
  });

  it('listWanted sends the bearer token', async () => {
    let auth: string | null = null;
    server.use(
      http.get(`${baseUrl}/api/wanted`, ({ request }) => {
        auth = request.headers.get('authorization');
        return HttpResponse.json([]);
      }),
    );
    await api.listWanted('tok');
    expect(auth).toBe('Bearer tok');
  });

  it('createWanted appends ?kind=', async () => {
    let url: string | null = null;
    server.use(
      http.post(`${baseUrl}/api/wanted`, ({ request }) => {
        url = request.url;
        return HttpResponse.json({ id: 'x' }, { status: 201 });
      }),
    );
    await api.createWanted('tok', 'one_shot', {
      target_date: '2026-05-25', start_time: '14:00', end_time: '16:00',
      num_slots: 2, partners: [], credentials: 'BLOB',
    });
    expect(url).toContain('kind=one_shot');
  });
});
```

- [ ] **Step 8: Create `web/src/api/endpoints.ts`**

```ts
import { request } from './client';
import type {
  CreateOneShotRequest,
  CreateRecurringRequest,
  EncryptRequest,
  EncryptResponse,
  LoginRequest,
  LoginResponse,
  PartnerListResponse,
  PatchWantedRequest,
  WantedKind,
  WantedResponse,
} from './types';

export function encryptCredentials(body: EncryptRequest): Promise<EncryptResponse> {
  return request('/api/encrypt-credentials', { method: 'POST', body });
}

export function login(body: LoginRequest): Promise<LoginResponse> {
  return request('/api/login', { method: 'POST', body });
}

export function listWanted(token: string): Promise<WantedResponse[]> {
  return request('/api/wanted', { token });
}

export function getWanted(token: string, id: string): Promise<WantedResponse> {
  return request(`/api/wanted/${id}`, { token });
}

export function createWanted(
  token: string,
  kind: WantedKind,
  body: CreateOneShotRequest | CreateRecurringRequest,
): Promise<WantedResponse> {
  return request(`/api/wanted?kind=${kind}`, { method: 'POST', body, token });
}

export function patchWanted(
  token: string,
  id: string,
  body: PatchWantedRequest,
): Promise<WantedResponse> {
  return request(`/api/wanted/${id}`, { method: 'PATCH', body, token });
}

export function deleteWanted(token: string, id: string): Promise<void> {
  return request(`/api/wanted/${id}`, { method: 'DELETE', token });
}

export function listPartners(token: string): Promise<PartnerListResponse> {
  return request('/api/partners', { token });
}
```

- [ ] **Step 9: Run endpoint tests, verify pass**

```bash
cd web && npm test -- src/api/
```

Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add web/src/api/ web/src/config.ts
git commit -m "feat(web): typed API client + endpoints"
```

---

## Task 5: Auth context + ProtectedRoute

**Files:**
- Create: `web/src/auth/AuthProvider.tsx`, `web/src/auth/useAuth.ts`, `web/src/auth/ProtectedRoute.tsx`
- Test: `web/src/auth/AuthProvider.test.tsx`, `web/src/auth/ProtectedRoute.test.tsx`

- [ ] **Step 1: Write failing test for `AuthProvider`**

`web/src/auth/AuthProvider.test.tsx`:

```tsx
import { act, render, screen } from '@testing-library/react';
import { describe, expect, it, beforeEach } from 'vitest';
import { AuthProvider } from './AuthProvider';
import { useAuth } from './useAuth';

function Probe() {
  const a = useAuth();
  return (
    <div>
      <span data-testid="token">{a.token ?? 'none'}</span>
      <span data-testid="user">{a.username ?? 'none'}</span>
      <button onClick={() => a.login('tok', 'alice', 'BLOB',
                                     new Date('2099-01-01').toISOString())}>L</button>
      <button onClick={() => a.logout()}>O</button>
    </div>
  );
}

describe('AuthProvider', () => {
  beforeEach(() => sessionStorage.clear());

  it('starts logged out', () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    expect(screen.getByTestId('token').textContent).toBe('none');
  });

  it('login() persists token + username to sessionStorage', () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    act(() => { screen.getByText('L').click(); });
    expect(screen.getByTestId('token').textContent).toBe('tok');
    expect(screen.getByTestId('user').textContent).toBe('alice');
    expect(sessionStorage.getItem('tsa.token')).toBe('tok');
    expect(sessionStorage.getItem('tsa.username')).toBe('alice');
  });

  it('logout() clears state and sessionStorage', () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    act(() => { screen.getByText('L').click(); });
    act(() => { screen.getByText('O').click(); });
    expect(screen.getByTestId('token').textContent).toBe('none');
    expect(sessionStorage.getItem('tsa.token')).toBeNull();
  });

  it('rehydrates token from sessionStorage', () => {
    sessionStorage.setItem('tsa.token', 'persisted');
    sessionStorage.setItem('tsa.username', 'bob');
    render(<AuthProvider><Probe /></AuthProvider>);
    expect(screen.getByTestId('token').textContent).toBe('persisted');
  });

  it('does not persist credentialsBlob across reload', () => {
    render(<AuthProvider><Probe /></AuthProvider>);
    act(() => { screen.getByText('L').click(); });
    expect(sessionStorage.getItem('tsa.credentialsBlob')).toBeNull();
  });
});
```

- [ ] **Step 2: Run test — expect failure**

```bash
cd web && npm test -- src/auth/AuthProvider.test
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create `web/src/auth/AuthProvider.tsx`**

```tsx
import { createContext, useCallback, useMemo, useState, type ReactNode } from 'react';

export interface AuthState {
  token: string | null;
  username: string | null;
  credentialsBlob: string | null;
  expiresAt: string | null;
}

export interface AuthContextValue extends AuthState {
  login: (token: string, username: string, credentialsBlob: string, expiresAt: string) => void;
  logout: () => void;
  setCredentialsBlob: (blob: string) => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = 'tsa.token';
const USER_KEY = 'tsa.username';
const EXP_KEY = 'tsa.expiresAt';

function readInitial(): AuthState {
  if (typeof window === 'undefined') {
    return { token: null, username: null, credentialsBlob: null, expiresAt: null };
  }
  return {
    token: sessionStorage.getItem(TOKEN_KEY),
    username: sessionStorage.getItem(USER_KEY),
    expiresAt: sessionStorage.getItem(EXP_KEY),
    credentialsBlob: null,
  };
}

export function AuthProvider({
  children,
  initial,
}: {
  children: ReactNode;
  initial?: Partial<AuthState>;
}) {
  const [state, setState] = useState<AuthState>(() => ({ ...readInitial(), ...initial }));

  const login = useCallback(
    (token: string, username: string, credentialsBlob: string, expiresAt: string) => {
      sessionStorage.setItem(TOKEN_KEY, token);
      sessionStorage.setItem(USER_KEY, username);
      sessionStorage.setItem(EXP_KEY, expiresAt);
      setState({ token, username, credentialsBlob, expiresAt });
    },
    [],
  );

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(EXP_KEY);
    setState({ token: null, username: null, credentialsBlob: null, expiresAt: null });
  }, []);

  const setCredentialsBlob = useCallback((blob: string) => {
    setState((s) => ({ ...s, credentialsBlob: blob }));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, logout, setCredentialsBlob }),
    [state, login, logout, setCredentialsBlob],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
```

- [ ] **Step 4: Create `web/src/auth/useAuth.ts`**

```ts
import { useContext } from 'react';
import { AuthContext, type AuthContextValue } from './AuthProvider';

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
```

- [ ] **Step 5: Run AuthProvider tests, verify pass**

```bash
cd web && npm test -- src/auth/AuthProvider.test
```

Expected: 5 passed.

- [ ] **Step 6: Write failing test for `ProtectedRoute`**

`web/src/auth/ProtectedRoute.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './AuthProvider';
import { ProtectedRoute } from './ProtectedRoute';

function setup(route: string, token: string | null) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider initial={{ token }}>
        <Routes>
          <Route path="/login" element={<div>LOGIN</div>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/secret" element={<div>SECRET</div>} />
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('ProtectedRoute', () => {
  it('renders children when authed', () => {
    setup('/secret', 'tok');
    expect(screen.getByText('SECRET')).toBeInTheDocument();
  });
  it('redirects to /login when no token', () => {
    setup('/secret', null);
    expect(screen.getByText('LOGIN')).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: Create `web/src/auth/ProtectedRoute.tsx`**

```tsx
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from './useAuth';

export function ProtectedRoute() {
  const { token } = useAuth();
  const location = useLocation();
  if (!token) return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}
```

- [ ] **Step 8: Run, verify pass**

```bash
cd web && npm test -- src/auth/
```

Expected: 7 passed.

- [ ] **Step 9: Commit**

```bash
git add web/src/auth/
git commit -m "feat(web): AuthProvider + ProtectedRoute"
```

---

## Task 6: Format helpers + Zod schemas

**Files:**
- Create: `web/src/lib/format.ts`, `web/src/lib/schemas.ts`
- Test: `web/src/lib/format.test.ts`, `web/src/lib/schemas.test.ts`

- [ ] **Step 1: Failing test for `format.ts`**

`web/src/lib/format.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { formatTargetDate, formatDayOfWeek, formatLastAttempt } from './format';

describe('format helpers', () => {
  it('formats a target date as "Sat 24 May"', () => {
    expect(formatTargetDate('2026-05-23')).toMatch(/^Sat\b.+May$/);
  });

  it('formats day_of_week with Monday=0', () => {
    expect(formatDayOfWeek(0)).toBe('Every Monday');
    expect(formatDayOfWeek(6)).toBe('Every Sunday');
  });

  it('returns "No attempts yet" for empty array', () => {
    expect(formatLastAttempt([])).toBe('No attempts yet');
  });

  it('summarises the most recent attempt', () => {
    const a = [
      { ts: '2026-05-19T10:00:00Z', target_date: '2026-05-20',
        outcome: 'no_slots' as const, booking_id: null, error: null },
      { ts: '2026-05-19T12:00:00Z', target_date: '2026-05-20',
        outcome: 'booked' as const, booking_id: 'B1', error: null },
    ];
    expect(formatLastAttempt(a)).toMatch(/booked/);
  });
});
```

- [ ] **Step 2: Implement `web/src/lib/format.ts`**

```ts
import type { Attempt } from '../api/types';

const DAYS = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
const SHORT_DAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

export function formatTargetDate(iso: string): string {
  // Treat as a local calendar date (no TZ shifting).
  const [y, m, d] = iso.split('-').map(Number);
  const date = new Date(y, m - 1, d);
  // JS getDay(): 0=Sun..6=Sat. Map to our Mon=0 ordering for short day lookup.
  const jsDow = date.getDay();
  const shortIdx = jsDow === 0 ? 6 : jsDow - 1;
  return `${SHORT_DAYS[shortIdx]} ${d} ${MONTHS[m - 1]}`;
}

export function formatDayOfWeek(dow: number): string {
  return `Every ${DAYS[dow] ?? '?'}`;
}

export function formatLastAttempt(attempts: Attempt[]): string {
  if (attempts.length === 0) return 'No attempts yet';
  const last = [...attempts].sort((a, b) => (a.ts < b.ts ? 1 : -1))[0];
  return `${relTime(last.ts)} · ${last.outcome}`;
}

function relTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 48) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}
```

- [ ] **Step 3: Run, verify pass**

```bash
cd web && npm test -- src/lib/format
```

Expected: 4 passed.

- [ ] **Step 4: Failing test for Zod schemas**

`web/src/lib/schemas.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { oneShotSchema, recurringSchema, loginSchema } from './schemas';

describe('schemas', () => {
  it('login requires non-empty username + pin', () => {
    expect(loginSchema.safeParse({ username: '', pin: 'x' }).success).toBe(false);
    expect(loginSchema.safeParse({ username: 'u', pin: 'p' }).success).toBe(true);
  });

  it('one-shot rejects end_time <= start_time', () => {
    const base = { target_date: '2026-05-25', start_time: '14:00', end_time: '14:00',
                   num_slots: 1, partners: [] };
    expect(oneShotSchema.safeParse(base).success).toBe(false);
  });

  it('one-shot accepts a valid window', () => {
    expect(oneShotSchema.safeParse({
      target_date: '2026-05-25', start_time: '14:00', end_time: '16:00',
      num_slots: 1, partners: [],
    }).success).toBe(true);
  });

  it('partners max length 3', () => {
    const base = { target_date: '2026-05-25', start_time: '14:00', end_time: '16:00',
                   num_slots: 1, partners: ['a','b','c','d'] };
    expect(oneShotSchema.safeParse(base).success).toBe(false);
  });

  it('recurring requires day_of_week 0..6', () => {
    const ok = { day_of_week: 0, start_time: '09:00', end_time: '11:00',
                 num_slots: 2, partners: [] };
    expect(recurringSchema.safeParse(ok).success).toBe(true);
    expect(recurringSchema.safeParse({ ...ok, day_of_week: 7 }).success).toBe(false);
  });
});
```

- [ ] **Step 5: Implement `web/src/lib/schemas.ts`**

```ts
import { z } from 'zod';

const HHMM = /^\d{2}:\d{2}$/;
const YMD  = /^\d{4}-\d{2}-\d{2}$/;
const E164 = /^\+[1-9]\d{1,14}$/;

export const loginSchema = z.object({
  username: z.string().min(1, 'Username required'),
  pin:      z.string().min(1, 'PIN required'),
});

const notifySchema = z.object({
  to:   z.string().regex(E164, 'Must be E.164, e.g. +14155551212'),
  from: z.string().regex(E164).optional().or(z.literal('').transform(() => undefined)),
}).optional();

const commonShape = {
  start_time: z.string().regex(HHMM),
  end_time:   z.string().regex(HHMM),
  num_slots:  z.number().int().min(1).max(4),
  partners:   z.array(z.string()).max(3),
  notify:     notifySchema,
};

function refineWindow<T extends { start_time: string; end_time: string }>(s: z.ZodType<T>) {
  return s.refine((v) => v.end_time > v.start_time, {
    message: 'End time must be after start time', path: ['end_time'],
  });
}

export const oneShotSchema = refineWindow(
  z.object({ target_date: z.string().regex(YMD), ...commonShape }),
);

export const recurringSchema = refineWindow(
  z.object({
    day_of_week: z.number().int().min(0).max(6),
    end_date: z.string().regex(YMD).optional().or(z.literal('').transform(() => undefined)),
    ...commonShape,
  }),
);

export const patchSchema = z.object({
  start_time: z.string().regex(HHMM).optional(),
  end_time:   z.string().regex(HHMM).optional(),
  num_slots:  z.number().int().min(1).max(4).optional(),
  partners:   z.array(z.string()).max(3).optional(),
  notify:     notifySchema,
});

export type LoginForm     = z.infer<typeof loginSchema>;
export type OneShotForm   = z.infer<typeof oneShotSchema>;
export type RecurringForm = z.infer<typeof recurringSchema>;
```

- [ ] **Step 6: Run, verify pass**

```bash
cd web && npm test -- src/lib/
```

Expected: 9 passed.

- [ ] **Step 7: Commit**

```bash
git add web/src/lib/
git commit -m "feat(web): format helpers + Zod schemas"
```

---

## Task 7: Data hooks (React Query)

**Files:**
- Create: `web/src/hooks/useWanted.ts`, `web/src/hooks/usePartners.ts`, `web/src/hooks/useLogin.ts`

This task is plain glue; tests live in the consuming page tests rather than per-hook. Hooks are written without TDD here — adding a test per hook would be ceremony with no extra coverage.

- [ ] **Step 1: Create `web/src/hooks/useWanted.ts`**

```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createWanted, deleteWanted, getWanted, listWanted, patchWanted,
} from '../api/endpoints';
import type {
  CreateOneShotRequest, CreateRecurringRequest, PatchWantedRequest, WantedKind,
} from '../api/types';
import { useAuth } from '../auth/useAuth';

export function useWantedList() {
  const { token } = useAuth();
  return useQuery({
    queryKey: ['wanted'],
    queryFn: () => listWanted(token!),
    enabled: !!token,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useWanted(id: string) {
  const { token } = useAuth();
  return useQuery({
    queryKey: ['wanted', id],
    queryFn: () => getWanted(token!, id),
    enabled: !!token,
  });
}

export function useCreateWanted() {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: {
      kind: WantedKind;
      body: CreateOneShotRequest | CreateRecurringRequest;
    }) => createWanted(token!, vars.kind, vars.body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['wanted'] }),
  });
}

export function usePatchWanted(id: string) {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PatchWantedRequest) => patchWanted(token!, id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['wanted'] });
      qc.invalidateQueries({ queryKey: ['wanted', id] });
    },
  });
}

export function useDeleteWanted() {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteWanted(token!, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['wanted'] }),
  });
}
```

- [ ] **Step 2: Create `web/src/hooks/usePartners.ts`**

```ts
import { useQuery } from '@tanstack/react-query';
import { listPartners } from '../api/endpoints';
import { useAuth } from '../auth/useAuth';

export function usePartners() {
  const { token } = useAuth();
  return useQuery({
    queryKey: ['partners'],
    queryFn: () => listPartners(token!).then((r) => r.partners),
    enabled: !!token,
    staleTime: 5 * 60_000,
  });
}
```

- [ ] **Step 3: Create `web/src/hooks/useLogin.ts`**

```ts
import { useMutation } from '@tanstack/react-query';
import { encryptCredentials, login } from '../api/endpoints';
import { useAuth } from '../auth/useAuth';

export function useLogin() {
  const auth = useAuth();
  return useMutation({
    mutationFn: async (vars: { username: string; pin: string }) => {
      const { credentials } = await encryptCredentials(vars);
      const { access_token, expires_at } = await login({ credentials });
      auth.login(access_token, vars.username, credentials, expires_at);
      return { access_token };
    },
  });
}
```

- [ ] **Step 4: Type-check**

```bash
cd web && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add web/src/hooks/
git commit -m "feat(web): data hooks (useWanted, usePartners, useLogin)"
```

---

## Task 8: UI primitives — StatusPill, ConfirmDialog, AttemptList

**Files:**
- Create: `web/src/components/StatusPill.tsx`, `web/src/components/ConfirmDialog.tsx`, `web/src/components/AttemptList.tsx`
- Test: `web/src/components/StatusPill.test.tsx`, `web/src/components/AttemptList.test.tsx`

- [ ] **Step 1: Failing test for `StatusPill`**

`web/src/components/StatusPill.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatusPill } from './StatusPill';

describe('StatusPill', () => {
  it.each(['pending','booked','expired','disabled'] as const)('renders %s', (s) => {
    render(<StatusPill status={s} />);
    expect(screen.getByText(s.toUpperCase())).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement `web/src/components/StatusPill.tsx`**

```tsx
import type { WantedStatus } from '../api/types';

const COLORS: Record<WantedStatus, string> = {
  pending:  'bg-blue-600 text-white',
  booked:   'bg-green-600 text-white',
  expired:  'bg-amber-600 text-white',
  disabled: 'bg-slate-600 text-slate-200',
};

export function StatusPill({ status }: { status: WantedStatus }) {
  return (
    <span className={`text-[11px] px-2 py-0.5 rounded-full ${COLORS[status]}`}>
      {status.toUpperCase()}
    </span>
  );
}
```

- [ ] **Step 3: Implement `web/src/components/ConfirmDialog.tsx`**

```tsx
import type { ReactNode } from 'react';

export function ConfirmDialog({
  open, title, body, confirmLabel = 'Confirm', onConfirm, onCancel,
}: {
  open: boolean;
  title: string;
  body?: ReactNode;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
         role="dialog" aria-modal="true">
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold mb-2">{title}</h3>
        {body && <div className="text-slate-300 mb-4">{body}</div>}
        <div className="flex justify-end gap-2">
          <button onClick={onCancel} className="px-3 py-1.5 rounded bg-slate-700">
            Cancel
          </button>
          <button onClick={onConfirm} className="px-3 py-1.5 rounded bg-red-600 text-white">
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Failing test for `AttemptList`**

`web/src/components/AttemptList.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AttemptList } from './AttemptList';

describe('AttemptList', () => {
  it('shows empty state', () => {
    render(<AttemptList attempts={[]} />);
    expect(screen.getByText('No attempts yet.')).toBeInTheDocument();
  });

  it('renders newest first with outcome + error', () => {
    render(<AttemptList attempts={[
      { ts: '2026-05-19T10:00:00Z', target_date: '2026-05-20',
        outcome: 'no_slots', booking_id: null, error: null },
      { ts: '2026-05-19T12:00:00Z', target_date: '2026-05-20',
        outcome: 'booking_failed', booking_id: null, error: 'partner unknown' },
    ]} />);
    const rows = screen.getAllByRole('listitem');
    expect(rows[0]).toHaveTextContent('booking_failed');
    expect(rows[0]).toHaveTextContent('partner unknown');
  });
});
```

- [ ] **Step 5: Implement `web/src/components/AttemptList.tsx`**

```tsx
import type { Attempt } from '../api/types';

export function AttemptList({ attempts }: { attempts: Attempt[] }) {
  if (attempts.length === 0) {
    return <p className="text-slate-400">No attempts yet.</p>;
  }
  const sorted = [...attempts].sort((a, b) => (a.ts < b.ts ? 1 : -1));
  return (
    <ul className="space-y-2">
      {sorted.map((a, i) => (
        <li key={i} className="border border-slate-800 rounded p-3">
          <div className="flex justify-between text-sm">
            <span>{new Date(a.ts).toLocaleString()}</span>
            <span className="font-mono">{a.outcome}</span>
          </div>
          {a.booking_id && (
            <div className="text-xs text-slate-400">booking: {a.booking_id}</div>
          )}
          {a.error && (
            <div className="text-xs text-red-400 mt-1">{a.error}</div>
          )}
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 6: Run all component tests**

```bash
cd web && npm test -- src/components/
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add web/src/components/
git commit -m "feat(web): StatusPill, ConfirmDialog, AttemptList"
```

---

## Task 9: PartnerPicker + NotifyFields + SlotFormFields

**Files:**
- Create: `web/src/components/PartnerPicker.tsx`, `web/src/components/NotifyFields.tsx`, `web/src/components/SlotFormFields.tsx`
- Test: `web/src/components/PartnerPicker.test.tsx`

- [ ] **Step 1: Failing test for `PartnerPicker`**

`web/src/components/PartnerPicker.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { server, baseUrl } from '../../test/handlers';
import { PartnerPicker } from './PartnerPicker';
import { AuthProvider } from '../auth/AuthProvider';

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider initial={{ token: 'tok' }}>{ui}</AuthProvider>
    </QueryClientProvider>,
  );
}

describe('PartnerPicker', () => {
  beforeAll(() => { window.__TSA_CONFIG__ = { apiBaseUrl: baseUrl }; });

  it('lists partners and toggles selection up to 3', async () => {
    server.use(http.get(`${baseUrl}/api/partners`, () =>
      HttpResponse.json({ partners: [
        { id: 'a', name: 'Alice' },
        { id: 'b', name: 'Bob' },
        { id: 'c', name: 'Carol' },
        { id: 'd', name: 'Dave' },
      ]}),
    ));
    const onChange = vi.fn();
    wrap(<PartnerPicker value={[]} onChange={onChange} />);
    expect(await screen.findByText('Alice')).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText('Alice'));
    expect(onChange).toHaveBeenLastCalledWith(['a']);
  });

  it('disables remaining checkboxes once 3 selected', async () => {
    server.use(http.get(`${baseUrl}/api/partners`, () =>
      HttpResponse.json({ partners: [
        { id: 'a', name: 'A' }, { id: 'b', name: 'B' },
        { id: 'c', name: 'C' }, { id: 'd', name: 'D' },
      ]}),
    ));
    wrap(<PartnerPicker value={['a','b','c']} onChange={() => {}} />);
    expect((await screen.findByLabelText('D'))).toBeDisabled();
    expect(screen.getByLabelText('A')).not.toBeDisabled();
  });
});
```

- [ ] **Step 2: Implement `web/src/components/PartnerPicker.tsx`**

```tsx
import { usePartners } from '../hooks/usePartners';

export function PartnerPicker({
  value, onChange,
}: { value: string[]; onChange: (next: string[]) => void }) {
  const { data: partners = [], isLoading } = usePartners();
  const atCap = value.length >= 3;

  function toggle(id: string) {
    if (value.includes(id)) onChange(value.filter((x) => x !== id));
    else if (!atCap) onChange([...value, id]);
  }

  if (isLoading) return <p className="text-slate-400">Loading partners…</p>;
  if (partners.length === 0) {
    return <p className="text-slate-400 text-sm">No partners configured.</p>;
  }
  return (
    <fieldset className="grid grid-cols-2 gap-2">
      <legend className="text-sm text-slate-300 mb-1">Partners (max 3)</legend>
      {partners.map((p) => {
        const checked = value.includes(p.id);
        return (
          <label key={p.id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              aria-label={p.name}
              checked={checked}
              disabled={!checked && atCap}
              onChange={() => toggle(p.id)}
            />
            {p.name}
          </label>
        );
      })}
    </fieldset>
  );
}
```

- [ ] **Step 3: Implement `web/src/components/NotifyFields.tsx`**

```tsx
import type { UseFormRegister, FieldErrors } from 'react-hook-form';

export function NotifyFields({
  register, errors,
}: { register: UseFormRegister<any>; errors: FieldErrors<any> }) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm text-slate-300">Notify (optional)</legend>
      <div>
        <label className="text-xs text-slate-400" htmlFor="notify-to">To (E.164)</label>
        <input id="notify-to" {...register('notify.to')}
               placeholder="+14155551212"
               className="block w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
        {errors.notify && (errors.notify as any).to && (
          <p className="text-xs text-red-400">{(errors.notify as any).to.message}</p>
        )}
      </div>
      <div>
        <label className="text-xs text-slate-400" htmlFor="notify-from">From (optional)</label>
        <input id="notify-from" {...register('notify.from')}
               className="block w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
      </div>
    </fieldset>
  );
}
```

- [ ] **Step 4: Implement `web/src/components/SlotFormFields.tsx`** (shared fields used by both forms)

```tsx
import { Controller, type Control, type UseFormRegister, type FieldErrors } from 'react-hook-form';
import { PartnerPicker } from './PartnerPicker';
import { NotifyFields } from './NotifyFields';

export function SlotFormFields({
  register, control, errors,
}: {
  register: UseFormRegister<any>;
  control: Control<any>;
  errors: FieldErrors<any>;
}) {
  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        <label className="text-sm">Start
          <input type="time" step={60} {...register('start_time')}
                 className="block w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
        </label>
        <label className="text-sm">End
          <input type="time" step={60} {...register('end_time')}
                 className="block w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
          {errors.end_time && (
            <p className="text-xs text-red-400">{String(errors.end_time.message)}</p>
          )}
        </label>
      </div>

      <label className="text-sm block">Slots
        <select {...register('num_slots', { valueAsNumber: true })}
                className="block bg-slate-900 border border-slate-700 rounded px-2 py-1">
          <option value={1}>1</option><option value={2}>2</option>
          <option value={3}>3</option><option value={4}>4</option>
        </select>
      </label>

      <Controller
        control={control}
        name="partners"
        render={({ field }) => (
          <PartnerPicker value={field.value ?? []} onChange={field.onChange} />
        )}
      />

      <NotifyFields register={register} errors={errors} />
    </>
  );
}
```

- [ ] **Step 5: Run, verify pass**

```bash
cd web && npm test -- src/components/PartnerPicker
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/
git commit -m "feat(web): PartnerPicker, NotifyFields, SlotFormFields"
```

---

## Task 10: WantedCard

**Files:**
- Create: `web/src/components/WantedCard.tsx`
- Test: `web/src/components/WantedCard.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { WantedCard } from './WantedCard';
import type { WantedResponse } from '../api/types';

const base: WantedResponse = {
  id: 'abc', kind: 'one_shot',
  target_date: '2026-05-23', day_of_week: null, end_date: null,
  start_time: '14:00', end_time: '16:30',
  num_slots: 4, partners: ['p1','p2'],
  has_credentials: true, notify: null,
  status: 'pending', attempts: [],
  created_at: '2026-05-19T00:00:00Z', updated_at: '2026-05-19T00:00:00Z',
};

describe('WantedCard', () => {
  it('renders one_shot title from target_date', () => {
    render(<MemoryRouter><WantedCard slot={base} /></MemoryRouter>);
    expect(screen.getByText(/Sat\b.+May/)).toBeInTheDocument();
    expect(screen.getByText('14:00–16:30 · 4 slots · 2 partners')).toBeInTheDocument();
    expect(screen.getByText('PENDING')).toBeInTheDocument();
    expect(screen.getByText('No attempts yet')).toBeInTheDocument();
  });

  it('renders recurring title from day_of_week', () => {
    render(<MemoryRouter><WantedCard slot={{
      ...base, kind: 'recurring', target_date: null, day_of_week: 6,
    }} /></MemoryRouter>);
    expect(screen.getByText('Every Sunday')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement `WantedCard.tsx`**

```tsx
import { Link } from 'react-router-dom';
import type { WantedResponse } from '../api/types';
import { StatusPill } from './StatusPill';
import { formatDayOfWeek, formatLastAttempt, formatTargetDate } from '../lib/format';

export function WantedCard({ slot }: { slot: WantedResponse }) {
  const title =
    slot.kind === 'one_shot' && slot.target_date
      ? formatTargetDate(slot.target_date)
      : slot.day_of_week != null
        ? formatDayOfWeek(slot.day_of_week)
        : '—';

  return (
    <Link to={`/wanted/${slot.id}`}
          className={`block border border-slate-700 rounded-lg p-3 hover:border-slate-500
                      ${slot.status === 'disabled' ? 'opacity-60' : ''}`}>
      <div className="flex justify-between items-start">
        <strong>{title}</strong>
        <StatusPill status={slot.status} />
      </div>
      <div className="text-sm text-slate-300 mt-1">
        {slot.start_time}–{slot.end_time} · {slot.num_slots} slots
        {slot.partners.length > 0 && ` · ${slot.partners.length} partners`}
      </div>
      <div className="text-xs text-slate-400 mt-1">{formatLastAttempt(slot.attempts)}</div>
    </Link>
  );
}
```

- [ ] **Step 3: Run, verify pass**

```bash
cd web && npm test -- src/components/WantedCard
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/WantedCard.*
git commit -m "feat(web): WantedCard"
```

---

## Task 11: LoginPage

**Files:**
- Create: `web/src/pages/LoginPage.tsx`
- Test: `web/src/pages/LoginPage.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server, baseUrl } from '../../test/handlers';
import { renderWithProviders } from '../../test/utils';
import { LoginPage } from './LoginPage';
import { Route, Routes } from 'react-router-dom';

describe('LoginPage', () => {
  beforeAll(() => { window.__TSA_CONFIG__ = { apiBaseUrl: baseUrl }; });

  it('logs in and navigates to /wanted', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/wanted" element={<div>LIST</div>} />
      </Routes>,
      { route: '/login' },
    );
    await userEvent.type(screen.getByLabelText(/username/i), 'alice');
    await userEvent.type(screen.getByLabelText(/pin/i), '1234');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() => expect(screen.getByText('LIST')).toBeInTheDocument());
    expect(sessionStorage.getItem('tsa.token')).toBe('test-token');
  });

  it('shows "Invalid username or PIN" on 401', async () => {
    server.use(http.post(`${baseUrl}/api/login`, () =>
      HttpResponse.json({ detail: 'bad creds' }, { status: 401 }),
    ));
    renderWithProviders(<LoginPage />, { route: '/login' });
    await userEvent.type(screen.getByLabelText(/username/i), 'alice');
    await userEvent.type(screen.getByLabelText(/pin/i), 'x');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));
    expect(await screen.findByText(/Invalid username or PIN/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement `LoginPage.tsx`**

```tsx
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import { useLogin } from '../hooks/useLogin';
import { loginSchema, type LoginForm } from '../lib/schemas';

export function LoginPage() {
  const navigate = useNavigate();
  const m = useLogin();
  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = handleSubmit(async (values) => {
    await m.mutateAsync(values);
    navigate('/wanted');
  });

  const errorMsg =
    m.error instanceof ApiError
      ? m.error.status === 401 ? 'Invalid username or PIN.'
      : m.error.status === 502 ? 'Booking site unreachable; try again shortly.'
      : `Login failed: ${m.error.detail}`
      : null;

  return (
    <main className="min-h-screen grid place-items-center">
      <form onSubmit={onSubmit}
            className="w-full max-w-sm bg-slate-900 p-6 rounded-lg border border-slate-700 space-y-3">
        <h1 className="text-xl font-semibold">Sign in</h1>
        <label className="block text-sm">Username
          <input {...register('username')} autoComplete="username"
                 className="block w-full bg-slate-950 border border-slate-700 rounded px-2 py-1" />
          {errors.username && <p className="text-xs text-red-400">{errors.username.message}</p>}
        </label>
        <label className="block text-sm">PIN
          <input type="password" {...register('pin')} autoComplete="current-password"
                 className="block w-full bg-slate-950 border border-slate-700 rounded px-2 py-1" />
          {errors.pin && <p className="text-xs text-red-400">{errors.pin.message}</p>}
        </label>
        {errorMsg && <p className="text-sm text-red-400">{errorMsg}</p>}
        <button type="submit" disabled={m.isPending}
                className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50
                           text-white rounded px-3 py-2">
          {m.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  );
}
```

- [ ] **Step 3: Run, verify pass**

```bash
cd web && npm test -- src/pages/LoginPage
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/LoginPage.*
git commit -m "feat(web): LoginPage"
```

---

## Task 12: WantedListPage

**Files:**
- Create: `web/src/pages/WantedListPage.tsx`
- Test: `web/src/pages/WantedListPage.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server, baseUrl } from '../../test/handlers';
import { renderWithProviders } from '../../test/utils';
import { WantedListPage } from './WantedListPage';
import type { WantedResponse } from '../api/types';

const fixtures: WantedResponse[] = [
  { id: '1', kind: 'one_shot', target_date: '2026-05-23',
    day_of_week: null, end_date: null,
    start_time: '14:00', end_time: '16:30', num_slots: 4, partners: [],
    has_credentials: true, notify: null, status: 'pending', attempts: [],
    created_at: '', updated_at: '' },
  { id: '2', kind: 'recurring', target_date: null, day_of_week: 0, end_date: null,
    start_time: '09:00', end_time: '11:00', num_slots: 2, partners: [],
    has_credentials: true, notify: null, status: 'disabled', attempts: [],
    created_at: '', updated_at: '' },
];

describe('WantedListPage', () => {
  beforeAll(() => { window.__TSA_CONFIG__ = { apiBaseUrl: baseUrl }; });

  it('lists cards and filters by status', async () => {
    server.use(http.get(`${baseUrl}/api/wanted`, () => HttpResponse.json(fixtures)));
    renderWithProviders(<WantedListPage />, { initialAuth: { token: 'tok', username: 'alice' } });

    expect(await screen.findByText(/Sat\b.+May/)).toBeInTheDocument();
    expect(screen.getByText('Every Monday')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /^Disabled$/ }));
    expect(screen.queryByText(/Sat\b.+May/)).not.toBeInTheDocument();
    expect(screen.getByText('Every Monday')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement `WantedListPage.tsx`**

```tsx
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';
import { useWantedList } from '../hooks/useWanted';
import { WantedCard } from '../components/WantedCard';
import type { WantedStatus } from '../api/types';

type Filter = 'all' | WantedStatus;
const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'pending', label: 'Pending' },
  { key: 'booked', label: 'Booked' },
  { key: 'disabled', label: 'Disabled' },
  { key: 'expired', label: 'Expired' },
];

export function WantedListPage() {
  const auth = useAuth();
  const { data: slots, isLoading, error } = useWantedList();
  const [filter, setFilter] = useState<Filter>('all');

  const filtered = (slots ?? []).filter((s) => filter === 'all' ? true : s.status === filter);

  return (
    <main className="max-w-5xl mx-auto p-6">
      <header className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold">Wanted tee-times</h1>
        <div className="flex items-center gap-3 text-sm">
          <Link to="/wanted/new"
                className="bg-blue-600 hover:bg-blue-500 text-white rounded px-3 py-1.5">
            + New
          </Link>
          <span className="text-slate-400">Logged in as {auth.username}</span>
          <button onClick={() => auth.logout()} className="text-slate-300 underline">Logout</button>
        </div>
      </header>

      <div className="flex gap-2 mb-4">
        {FILTERS.map((f) => (
          <button key={f.key}
                  onClick={() => setFilter(f.key)}
                  className={`text-sm px-3 py-1 rounded-full border
                              ${filter === f.key
                                ? 'bg-slate-700 border-slate-500'
                                : 'border-slate-700 hover:border-slate-500'}`}>
            {f.label}
          </button>
        ))}
      </div>

      {isLoading && <p className="text-slate-400">Loading…</p>}
      {error && <p className="text-red-400">Failed to load wanted slots.</p>}
      {!isLoading && filtered.length === 0 && (
        <p className="text-slate-400">No wanted slots match this filter.</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {filtered.map((s) => <WantedCard key={s.id} slot={s} />)}
      </div>
    </main>
  );
}
```

- [ ] **Step 3: Run, verify pass**

```bash
cd web && npm test -- src/pages/WantedListPage
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/WantedListPage.*
git commit -m "feat(web): WantedListPage"
```

---

## Task 13: WantedNewPage (OneShotForm + RecurringForm)

**Files:**
- Create: `web/src/components/OneShotForm.tsx`, `web/src/components/RecurringForm.tsx`, `web/src/pages/WantedNewPage.tsx`
- Test: `web/src/pages/WantedNewPage.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server, baseUrl } from '../../test/handlers';
import { renderWithProviders } from '../../test/utils';
import { WantedNewPage } from './WantedNewPage';
import { Route, Routes } from 'react-router-dom';

describe('WantedNewPage', () => {
  beforeAll(() => { window.__TSA_CONFIG__ = { apiBaseUrl: baseUrl }; });

  it('submits a one-shot wanted slot and navigates back to /wanted', async () => {
    let received: { url: string; body: any } | null = null;
    server.use(http.post(`${baseUrl}/api/wanted`, async ({ request }) => {
      received = { url: request.url, body: await request.json() };
      return HttpResponse.json({ id: 'new' }, { status: 201 });
    }));

    renderWithProviders(
      <Routes>
        <Route path="/wanted/new" element={<WantedNewPage />} />
        <Route path="/wanted" element={<div>LIST</div>} />
      </Routes>,
      {
        route: '/wanted/new',
        initialAuth: { token: 'tok', credentialsBlob: 'BLOB' },
      },
    );

    await userEvent.type(screen.getByLabelText(/target date/i), '2026-05-25');
    await userEvent.clear(screen.getByLabelText(/^start$/i));
    await userEvent.type(screen.getByLabelText(/^start$/i), '14:00');
    await userEvent.clear(screen.getByLabelText(/^end$/i));
    await userEvent.type(screen.getByLabelText(/^end$/i), '16:00');
    await userEvent.click(screen.getByRole('button', { name: /create/i }));

    await waitFor(() => expect(screen.getByText('LIST')).toBeInTheDocument());
    expect(received!.url).toContain('kind=one_shot');
    expect(received!.body.credentials).toBe('BLOB');
    expect(received!.body.target_date).toBe('2026-05-25');
  });

  it('toggles to Recurring mode', async () => {
    renderWithProviders(<WantedNewPage />, {
      route: '/wanted/new',
      initialAuth: { token: 'tok', credentialsBlob: 'BLOB' },
    });
    await userEvent.click(screen.getByRole('tab', { name: /recurring/i }));
    expect(screen.getByLabelText(/day of week/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement `OneShotForm.tsx`**

```tsx
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { SlotFormFields } from './SlotFormFields';
import { oneShotSchema, type OneShotForm as OneShotValues } from '../lib/schemas';

export interface OneShotSubmit extends OneShotValues {}

const today = new Date().toISOString().slice(0, 10);
const plus7 = new Date(Date.now() + 7 * 86400_000).toISOString().slice(0, 10);

export function OneShotForm({ onSubmit, busy }: {
  onSubmit: (v: OneShotSubmit) => void; busy: boolean;
}) {
  const { register, handleSubmit, control, formState: { errors } } = useForm<OneShotValues>({
    resolver: zodResolver(oneShotSchema),
    defaultValues: { num_slots: 1, partners: [] },
  });
  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
      <label className="text-sm block">Target date
        <input type="date" min={today} max={plus7}
               {...register('target_date')}
               className="block bg-slate-900 border border-slate-700 rounded px-2 py-1" />
        {errors.target_date && (
          <p className="text-xs text-red-400">{errors.target_date.message}</p>
        )}
      </label>
      <SlotFormFields register={register} control={control} errors={errors} />
      <button type="submit" disabled={busy}
              className="bg-blue-600 hover:bg-blue-500 text-white rounded px-3 py-2 disabled:opacity-50">
        {busy ? 'Creating…' : 'Create'}
      </button>
    </form>
  );
}
```

- [ ] **Step 3: Implement `RecurringForm.tsx`**

```tsx
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { SlotFormFields } from './SlotFormFields';
import { recurringSchema, type RecurringForm as RecurringValues } from '../lib/schemas';

const DAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];

export function RecurringForm({ onSubmit, busy }: {
  onSubmit: (v: RecurringValues) => void; busy: boolean;
}) {
  const { register, handleSubmit, control, formState: { errors } } = useForm<RecurringValues>({
    resolver: zodResolver(recurringSchema),
    defaultValues: { num_slots: 1, partners: [], day_of_week: 0 },
  });
  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
      <label className="text-sm block">Day of week
        <select {...register('day_of_week', { valueAsNumber: true })}
                className="block bg-slate-900 border border-slate-700 rounded px-2 py-1">
          {DAYS.map((d, i) => <option key={i} value={i}>{d}</option>)}
        </select>
      </label>
      <label className="text-sm block">End date (optional)
        <input type="date" {...register('end_date')}
               className="block bg-slate-900 border border-slate-700 rounded px-2 py-1" />
      </label>
      <SlotFormFields register={register} control={control} errors={errors} />
      <button type="submit" disabled={busy}
              className="bg-blue-600 hover:bg-blue-500 text-white rounded px-3 py-2 disabled:opacity-50">
        {busy ? 'Creating…' : 'Create'}
      </button>
    </form>
  );
}
```

- [ ] **Step 4: Implement `WantedNewPage.tsx`**

```tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ApiError } from '../api/client';
import { useAuth } from '../auth/useAuth';
import { useCreateWanted } from '../hooks/useWanted';
import { OneShotForm } from '../components/OneShotForm';
import { RecurringForm } from '../components/RecurringForm';
import { encryptCredentials } from '../api/endpoints';

type Mode = 'one_shot' | 'recurring';

export function WantedNewPage() {
  const [mode, setMode] = useState<Mode>('one_shot');
  const [pinPrompt, setPinPrompt] = useState<{ user: string; pin: string }>({ user: '', pin: '' });
  const auth = useAuth();
  const navigate = useNavigate();
  const m = useCreateWanted();

  async function obtainBlob(): Promise<string> {
    if (auth.credentialsBlob) return auth.credentialsBlob;
    if (!auth.username) throw new Error('Not authenticated');
    if (!pinPrompt.pin) throw new Error('Re-enter PIN to save');
    const { credentials } = await encryptCredentials({
      username: auth.username, pin: pinPrompt.pin,
    });
    auth.setCredentialsBlob(credentials);
    return credentials;
  }

  async function submit(values: any) {
    try {
      const credentials = await obtainBlob();
      await m.mutateAsync({ kind: mode, body: { ...values, credentials } });
      toast.success('Wanted slot created');
      navigate('/wanted');
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : (e as Error).message;
      toast.error(msg);
    }
  }

  return (
    <main className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-semibold mb-4">New wanted slot</h1>
      <div role="tablist" className="inline-flex bg-slate-900 rounded p-1 mb-4">
        <button role="tab" aria-selected={mode === 'one_shot'}
                onClick={() => setMode('one_shot')}
                className={`px-3 py-1 rounded ${mode === 'one_shot' ? 'bg-slate-700' : ''}`}>
          One-shot
        </button>
        <button role="tab" aria-selected={mode === 'recurring'}
                onClick={() => setMode('recurring')}
                className={`px-3 py-1 rounded ${mode === 'recurring' ? 'bg-slate-700' : ''}`}>
          Recurring
        </button>
      </div>

      {!auth.credentialsBlob && (
        <div className="mb-4 border border-amber-700/50 bg-amber-900/20 rounded p-3 text-sm">
          <p className="mb-2">Re-enter your PIN to save credentials to this slot.</p>
          <input type="password" placeholder="PIN"
                 value={pinPrompt.pin}
                 onChange={(e) => setPinPrompt({ user: auth.username ?? '', pin: e.target.value })}
                 className="bg-slate-950 border border-slate-700 rounded px-2 py-1" />
        </div>
      )}

      {mode === 'one_shot'
        ? <OneShotForm onSubmit={submit} busy={m.isPending} />
        : <RecurringForm onSubmit={submit} busy={m.isPending} />}
    </main>
  );
}
```

- [ ] **Step 5: Run, verify pass**

```bash
cd web && npm test -- src/pages/WantedNewPage
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/WantedNewPage.* web/src/components/OneShotForm.* web/src/components/RecurringForm.*
git commit -m "feat(web): WantedNewPage with one-shot + recurring forms"
```

---

## Task 14: WantedDetailPage

**Files:**
- Create: `web/src/pages/WantedDetailPage.tsx`
- Test: `web/src/pages/WantedDetailPage.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server, baseUrl } from '../../test/handlers';
import { renderWithProviders } from '../../test/utils';
import { WantedDetailPage } from './WantedDetailPage';
import { Route, Routes } from 'react-router-dom';
import type { WantedResponse } from '../api/types';

const slot: WantedResponse = {
  id: 'abc', kind: 'one_shot', target_date: '2026-05-23',
  day_of_week: null, end_date: null,
  start_time: '14:00', end_time: '16:30', num_slots: 4, partners: [],
  has_credentials: true, notify: null, status: 'pending',
  attempts: [{ ts: '2026-05-19T10:00:00Z', target_date: '2026-05-23',
               outcome: 'no_slots', booking_id: null, error: null }],
  created_at: '', updated_at: '',
};

describe('WantedDetailPage', () => {
  beforeAll(() => { window.__TSA_CONFIG__ = { apiBaseUrl: baseUrl }; });

  it('shows attempts and supports delete', async () => {
    server.use(
      http.get(`${baseUrl}/api/wanted/abc`, () => HttpResponse.json(slot)),
      http.delete(`${baseUrl}/api/wanted/abc`, () =>
        new HttpResponse(null, { status: 204 }),
      ),
    );
    renderWithProviders(
      <Routes>
        <Route path="/wanted/:id" element={<WantedDetailPage />} />
        <Route path="/wanted" element={<div>LIST</div>} />
      </Routes>,
      { route: '/wanted/abc', initialAuth: { token: 'tok' } },
    );
    expect(await screen.findByText('no_slots')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /delete/i }));
    await userEvent.click(screen.getByRole('button', { name: /^confirm$/i }));
    await waitFor(() => expect(screen.getByText('LIST')).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Implement `WantedDetailPage.tsx`**

```tsx
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ApiError } from '../api/client';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { AttemptList } from '../components/AttemptList';
import { StatusPill } from '../components/StatusPill';
import { useDeleteWanted, usePatchWanted, useWanted } from '../hooks/useWanted';

export function WantedDetailPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { data: slot, isLoading } = useWanted(id);
  const patch = usePatchWanted(id);
  const del = useDeleteWanted();
  const [confirming, setConfirming] = useState(false);
  const [form, setForm] = useState({ start_time: '', end_time: '', num_slots: 1 });

  if (isLoading || !slot) return <main className="p-6 text-slate-400">Loading…</main>;

  // Initialise form from slot the first time it loads.
  if (form.start_time === '') {
    setForm({ start_time: slot.start_time, end_time: slot.end_time, num_slots: slot.num_slots });
  }

  async function save() {
    try { await patch.mutateAsync(form); toast.success('Saved'); }
    catch (e) { toast.error(e instanceof ApiError ? e.detail : String(e)); }
  }

  async function toggleDisabled() {
    try {
      await patch.mutateAsync({ disabled: slot.status !== 'disabled' });
    } catch (e) { toast.error(e instanceof ApiError ? e.detail : String(e)); }
  }

  async function confirmDelete() {
    try {
      await del.mutateAsync(slot.id);
      toast.success('Deleted');
      navigate('/wanted');
    } catch (e) { toast.error(e instanceof ApiError ? e.detail : String(e)); }
  }

  return (
    <main className="max-w-5xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
      <section>
        <div className="flex items-center justify-between mb-3">
          <h1 className="text-xl font-semibold">Edit</h1>
          <StatusPill status={slot.status} />
        </div>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <label className="text-sm">Start
              <input type="time" value={form.start_time}
                     onChange={(e) => setForm({ ...form, start_time: e.target.value })}
                     className="block w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
            </label>
            <label className="text-sm">End
              <input type="time" value={form.end_time}
                     onChange={(e) => setForm({ ...form, end_time: e.target.value })}
                     className="block w-full bg-slate-900 border border-slate-700 rounded px-2 py-1" />
            </label>
          </div>
          <label className="text-sm block">Slots
            <select value={form.num_slots}
                    onChange={(e) => setForm({ ...form, num_slots: Number(e.target.value) })}
                    className="block bg-slate-900 border border-slate-700 rounded px-2 py-1">
              <option value={1}>1</option><option value={2}>2</option>
              <option value={3}>3</option><option value={4}>4</option>
            </select>
          </label>
          <div className="flex gap-2">
            <button onClick={save} disabled={patch.isPending}
                    className="bg-blue-600 hover:bg-blue-500 text-white rounded px-3 py-1.5">
              Save
            </button>
            <button onClick={toggleDisabled}
                    className="bg-slate-700 hover:bg-slate-600 rounded px-3 py-1.5">
              {slot.status === 'disabled' ? 'Enable' : 'Disable'}
            </button>
            <button onClick={() => setConfirming(true)}
                    className="bg-red-700 hover:bg-red-600 text-white rounded px-3 py-1.5 ml-auto">
              Delete
            </button>
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-3">Attempts</h2>
        <AttemptList attempts={slot.attempts} />
      </section>

      <ConfirmDialog
        open={confirming}
        title="Delete this wanted slot?"
        body="This cannot be undone."
        confirmLabel="Confirm"
        onConfirm={confirmDelete}
        onCancel={() => setConfirming(false)}
      />
    </main>
  );
}
```

- [ ] **Step 3: Run, verify pass**

```bash
cd web && npm test -- src/pages/WantedDetailPage
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/WantedDetailPage.*
git commit -m "feat(web): WantedDetailPage with edit/disable/delete"
```

---

## Task 15: App + Router + global Toaster, replace placeholder

**Files:**
- Create: `web/src/router.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: Create `web/src/router.tsx`**

```tsx
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';
import { LoginPage } from './pages/LoginPage';
import { WantedListPage } from './pages/WantedListPage';
import { WantedNewPage } from './pages/WantedNewPage';
import { WantedDetailPage } from './pages/WantedDetailPage';
import { ProtectedRoute } from './auth/ProtectedRoute';

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      { path: '/wanted', element: <WantedListPage /> },
      { path: '/wanted/new', element: <WantedNewPage /> },
      { path: '/wanted/:id', element: <WantedDetailPage /> },
    ],
  },
  { path: '*', element: <Navigate to="/wanted" replace /> },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
```

- [ ] **Step 2: Replace `web/src/App.tsx`**

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { AuthProvider } from './auth/AuthProvider';
import { AppRouter } from './router';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: true, retry: false },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppRouter />
        <Toaster theme="dark" position="top-right" richColors />
      </AuthProvider>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 3: Type-check and full test run**

```bash
cd web && npx tsc --noEmit && npm test
```

Expected: no type errors; all tests pass.

- [ ] **Step 4: Build smoke test**

```bash
cd web && npm run build
```

Expected: `dist/index.html`, `dist/assets/*.js` produced.

- [ ] **Step 5: Manual dev smoke test** (optional, requires running API on :8000)

```bash
cd web && npm run dev
# Open http://localhost:5173 → /login should render.
```

- [ ] **Step 6: Commit**

```bash
git add web/src/App.tsx web/src/router.tsx
git commit -m "feat(web): wire App, router, Toaster"
```

---

## Task 16: Dockerfile + nginx + runtime config

**Files:**
- Create: `web/Dockerfile`, `web/nginx.conf`, `web/entrypoint.sh`

- [ ] **Step 1: Create `web/nginx.conf`**

```nginx
server {
  listen 80;
  root /usr/share/nginx/html;
  index index.html;

  # SPA fallback
  location / {
    try_files $uri /index.html;
  }

  # Long-cache hashed assets
  location /assets/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
  }

  # config.js is rewritten at container start; never cache.
  location = /config.js {
    add_header Cache-Control "no-store";
  }
}
```

- [ ] **Step 2: Create `web/entrypoint.sh`**

```sh
#!/bin/sh
set -e
: "${API_BASE_URL:=}"
cat > /usr/share/nginx/html/config.js <<EOF
window.__TSA_CONFIG__ = { apiBaseUrl: "${API_BASE_URL}" };
EOF
exec nginx -g 'daemon off;'
```

Make executable (the Dockerfile will also `chmod` it):

```bash
chmod +x web/entrypoint.sh
```

- [ ] **Step 3: Create `web/Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]
```

- [ ] **Step 4: Local docker build smoke test**

```bash
cd web && docker build -t tee-sniper-web:dev .
docker run --rm -p 8080:80 -e API_BASE_URL=http://host.docker.internal:8000 \
           tee-sniper-web:dev &
sleep 2
curl -sI http://localhost:8080/ | head -1     # expect 200
curl -s  http://localhost:8080/config.js      # expect window.__TSA_CONFIG__
docker stop $(docker ps -q --filter ancestor=tee-sniper-web:dev)
```

Expected: index.html served, `/config.js` contains the env-injected base URL.

- [ ] **Step 5: Commit**

```bash
git add web/Dockerfile web/nginx.conf web/entrypoint.sh
git commit -m "build(web): Dockerfile + nginx + runtime config.js"
```

---

## Task 17: Helm chart `charts/tee-sniper-web`

**Files:**
- Create: `charts/tee-sniper-web/Chart.yaml`, `values.yaml`, `templates/_helpers.tpl`, `templates/deployment.yaml`, `templates/service.yaml`, `templates/ingress.yaml`, `templates/configmap.yaml`

Mirror the structure of `charts/tee-sniper-api`. Inspect that chart first and reuse its naming conventions for `_helpers.tpl`.

- [ ] **Step 1: Read the existing API chart for conventions**

```bash
ls charts/tee-sniper-api/templates/
cat charts/tee-sniper-api/Chart.yaml
cat charts/tee-sniper-api/values.yaml
```

Use the same labels, helpers, image-pull-secret patterns.

- [ ] **Step 2: Create `charts/tee-sniper-web/Chart.yaml`**

```yaml
apiVersion: v2
name: tee-sniper-web
description: nginx-served React UI for tee-sniper wanted tee-times
type: application
version: 0.1.0
appVersion: "0.1.0"
```

- [ ] **Step 3: Create `charts/tee-sniper-web/values.yaml`**

```yaml
image:
  repository: ghcr.io/<owner>/tee-sniper-web
  tag: ""              # defaults to .Chart.AppVersion
  pullPolicy: IfNotPresent

replicaCount: 1

service:
  type: ClusterIP
  port: 80

# Empty string → browser uses relative /api/* (same-host ingress).
apiBaseUrl: ""

ingress:
  enabled: true
  className: ""
  annotations: {}
  host: tee-sniper.example.com
  tls:
    enabled: false
    secretName: ""
  # Path-based split: /api/* → API service, /* → this service.
  apiServiceName: tee-sniper-api
  apiServicePort: 80

resources:
  limits:   { cpu: 100m, memory: 64Mi }
  requests: { cpu: 10m,  memory: 32Mi }

nodeSelector: {}
tolerations: []
affinity: {}
```

Replace `<owner>` with the actual GHCR org (matching the API chart).

- [ ] **Step 4: Create `charts/tee-sniper-web/templates/_helpers.tpl`**

```yaml
{{- define "tee-sniper-web.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "tee-sniper-web.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "tee-sniper-web.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "tee-sniper-web.labels" -}}
app.kubernetes.io/name: {{ include "tee-sniper-web.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "tee-sniper-web.selectorLabels" -}}
app.kubernetes.io/name: {{ include "tee-sniper-web.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
```

- [ ] **Step 5: Create `templates/deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "tee-sniper-web.fullname" . }}
  labels: {{- include "tee-sniper-web.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels: {{- include "tee-sniper-web.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels: {{- include "tee-sniper-web.selectorLabels" . | nindent 8 }}
    spec:
      containers:
        - name: web
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - containerPort: 80
          env:
            - name: API_BASE_URL
              value: {{ .Values.apiBaseUrl | quote }}
          readinessProbe:
            httpGet: { path: /, port: 80 }
          livenessProbe:
            httpGet: { path: /, port: 80 }
          resources: {{- toYaml .Values.resources | nindent 12 }}
      {{- with .Values.nodeSelector }}
      nodeSelector: {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations: {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.affinity }}
      affinity: {{- toYaml . | nindent 8 }}
      {{- end }}
```

- [ ] **Step 6: Create `templates/service.yaml`**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "tee-sniper-web.fullname" . }}
  labels: {{- include "tee-sniper-web.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: 80
      protocol: TCP
      name: http
  selector: {{- include "tee-sniper-web.selectorLabels" . | nindent 4 }}
```

- [ ] **Step 7: Create `templates/ingress.yaml`**

```yaml
{{- if .Values.ingress.enabled -}}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "tee-sniper-web.fullname" . }}
  labels: {{- include "tee-sniper-web.labels" . | nindent 4 }}
  {{- with .Values.ingress.annotations }}
  annotations: {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  {{- with .Values.ingress.className }}
  ingressClassName: {{ . }}
  {{- end }}
  {{- if .Values.ingress.tls.enabled }}
  tls:
    - hosts: [{{ .Values.ingress.host | quote }}]
      secretName: {{ .Values.ingress.tls.secretName }}
  {{- end }}
  rules:
    - host: {{ .Values.ingress.host | quote }}
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: {{ .Values.ingress.apiServiceName }}
                port: { number: {{ .Values.ingress.apiServicePort }} }
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {{ include "tee-sniper-web.fullname" . }}
                port: { number: {{ .Values.service.port }} }
{{- end }}
```

- [ ] **Step 8: Lint and template-render**

```bash
helm lint charts/tee-sniper-web
helm template charts/tee-sniper-web > /tmp/web-render.yaml
head -40 /tmp/web-render.yaml
```

Expected: lint passes, render contains Deployment + Service + Ingress.

- [ ] **Step 9: Commit**

```bash
git add charts/tee-sniper-web/
git commit -m "build(charts): add tee-sniper-web Helm chart"
```

---

## Task 18: CI workflow

**Files:**
- Create: `.github/workflows/web-build.yml`

- [ ] **Step 1: Read the existing API workflow for parity**

```bash
cat .github/workflows/api-build.yml
```

Match its triggers, permissions, image-push strategy.

- [ ] **Step 2: Create `.github/workflows/web-build.yml`**

```yaml
name: web build

on:
  push:
    branches: [main]
    paths:
      - 'web/**'
      - '.github/workflows/web-build.yml'
  pull_request:
    paths:
      - 'web/**'
      - '.github/workflows/web-build.yml'

permissions:
  contents: read
  packages: write

jobs:
  test:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: web } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: web/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm test -- --reporter=default
      - run: npm run build

  image:
    needs: test
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: web
          push: true
          tags: |
            ghcr.io/${{ github.repository }}-web:latest
            ghcr.io/${{ github.repository }}-web:${{ github.sha }}
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/web-build.yml
git commit -m "ci: add web-build workflow"
```

---

## Task 19: Documentation — `web/README.md` and `CLAUDE.md`

**Files:**
- Create: `web/README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Create `web/README.md`**

```markdown
# tee-sniper-web

React SPA for the wanted tee-times workflow. Calls the FastAPI backend at
`/api/*` (configurable via `API_BASE_URL` at container start).

## Stack

Vite + React 18 + TypeScript + Tailwind + TanStack Query + React Router +
Zod + react-hook-form + sonner. Tests use Vitest + React Testing Library +
MSW.

## Development

```bash
cd web
npm install
npm run dev          # serves on :5173, proxies /api → http://localhost:8000
```

Run the API alongside (see top-level CLAUDE.md). The login flow needs both.

## Testing

```bash
npm test             # vitest run
npm run test:watch
npm run lint
npm run build
```

## Configuration

The browser reads its API base URL from `window.__TSA_CONFIG__.apiBaseUrl`,
which is rewritten by `entrypoint.sh` from the `API_BASE_URL` env var at
container start. Default `""` → relative `/api/*` requests (works when the
ingress routes `/api/*` to the API service on the same host).

## Deployment

Built into a multi-stage Docker image (`web/Dockerfile`) and deployed by
the Helm chart at `charts/tee-sniper-web`.
```

- [ ] **Step 2: Append a Web UI section to `CLAUDE.md`**

Insert after the existing "MCP Plan History" section:

```markdown
## Web UI (`web/`)

React SPA for the wanted tee-times workflow. Login + full CRUD over
`/api/wanted`. Stack: Vite + React + TypeScript + Tailwind + TanStack
Query + React Router + Zod + react-hook-form + Vitest + MSW. Deployed via
`charts/tee-sniper-web` (nginx serving the `dist/` baked into the image).

```bash
cd web
npm install
npm run dev    # :5173, proxies /api to http://localhost:8000
npm test
npm run build
```

The browser never sees the AES shared secret. It calls
`POST /api/encrypt-credentials` (added in this iteration) to get an
encrypted blob used by `/api/login` and by wanted-slot create.

- Spec: `docs/superpowers/specs/2026-05-20-wanted-tee-times-ui-design.md`
- Plan: `docs/superpowers/plans/2026-05-20-wanted-tee-times-ui.md`
```

- [ ] **Step 3: Commit**

```bash
git add web/README.md CLAUDE.md
git commit -m "docs: web/ README + CLAUDE.md web UI section"
```

---

## Task 20: Final verification

- [ ] **Step 1: Whole-repo regression — API tests**

```bash
cd api && .venv/bin/python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 2: Whole-repo regression — Go tests**

```bash
cd /Users/stevebennett/Code/tee-sniper-web-ui
go test ./...
```

Expected: all pass (Go side untouched, sanity check).

- [ ] **Step 3: Whole-repo regression — web tests**

```bash
cd web && npm run lint && npm test && npm run build
```

Expected: lint clean, all tests pass, build succeeds.

- [ ] **Step 4: Helm lint**

```bash
helm lint charts/tee-sniper-web charts/tee-sniper-api
```

Expected: both pass.

- [ ] **Step 5: Verify branch state for PR**

```bash
git log --oneline origin/main..HEAD
git status
```

Expected: ~20 atomic commits on `web/wanted-ui`, clean working tree.

- [ ] **Step 6: Controller pushes branch and opens PR**

The controller (not the implementer subagent) runs:

```bash
git push -u origin web/wanted-ui
gh pr create --base main --head web/wanted-ui \
  --title "Wanted tee-times web UI" \
  --body "$(cat <<'EOF'
Implements the React SPA for wanted tee-times per
`docs/superpowers/specs/2026-05-20-wanted-tee-times-ui-design.md`.

- New `web/` package (Vite + React + TS + Tailwind + TanStack Query)
- New `POST /api/encrypt-credentials` endpoint
- New `charts/tee-sniper-web` Helm chart (nginx ingress shares the host
  with the API chart: `/api/*` → API, `/*` → web)
- New `.github/workflows/web-build.yml` (test + build + GHCR image push)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review notes

- Spec coverage: login + CRUD pages, encrypt endpoint, auth lifecycle, partner picker, attempt timeline, error handling, MSW tests, Dockerfile, Helm chart, CI, docs — each maps to a task.
- Placeholders: none — every step has concrete code or commands.
- Type consistency: `WantedResponse`, `CreateOneShotRequest`, `CreateRecurringRequest`, `PatchWantedRequest`, `Partner`, `Attempt`, `Notify` are defined once in `api/types.ts` and reused. `useAuth().login` signature matches `AuthProvider`'s exposed contract throughout.
- One known nit deferred to implementation: `Task 14`'s detail-page form initialises with a `setState` during render guarded by `start_time === ''`. If React StrictMode causes the double-invoke to look weird in dev, swap to a `useEffect`. Functionally equivalent; left as-is for plan brevity.
