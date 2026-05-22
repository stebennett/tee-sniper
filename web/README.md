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
