# Helm-based Kubernetes Deployment — Design

**Date:** 2026-05-03
**Related:** GitHub Epic #30 (Phase 7), Issue #28
**Supersedes:** the raw-manifests/Kustomize approach in issue #28

## Goal

Deploy `tee-sniper-api` (FastAPI) plus its Redis dependency to a self-hosted k3s cluster via a single Helm chart, and schedule N booking runs as CronJobs that invoke `tee-sniper-cli` against the in-cluster API.

## Scope

In scope:
- One Helm chart: `charts/tee-sniper-api/`
- Bitnami Redis pulled in as a subchart dependency
- API Deployment + ClusterIP Service
- CronJob template that ranges over a `cronjobs:` list in values
- Two environment value files: `values-dev.yaml`, `values-prod.yaml`
- Optional, opt-in NetworkPolicy
- Helm linting + manifest validation in CI
- README documenting install, upgrade, secret contract, troubleshooting

Out of scope:
- HPA / autoscaling
- Redis HA (Sentinel / Cluster)
- Ingress, TLS, cert-manager (cluster-internal API only)
- Prometheus ServiceMonitor / metrics
- Sealed Secrets / SOPS / in-chart secret generation (secrets are managed externally by the user's 1Password operator)

## Target environment

- Self-hosted k3s
- Default ingress (Traefik) — unused, no Ingress resource shipped
- Default storage class `local-path` for Redis persistence
- Secrets created out-of-band by the user's 1Password external operator; the chart only references them by name

## Repository layout

```
charts/
  tee-sniper-api/
    Chart.yaml                 # depends on bitnami/redis (pinned version)
    Chart.lock                 # committed
    values.yaml                # production-ready defaults
    values-dev.yaml            # dev overrides
    values-prod.yaml           # prod overrides
    values.schema.json         # validates required fields, rejects tag: latest
    templates/
      _helpers.tpl
      deployment.yaml          # API
      service.yaml             # ClusterIP
      serviceaccount.yaml
      configmap.yaml           # non-secret API config
      cronjob.yaml             # range .Values.cronjobs
      networkpolicy.yaml       # gated by .Values.networkPolicy.enabled
      NOTES.txt
    charts/                    # populated by `helm dep update`, .gitignored
  README.md                    # install/upgrade/secret contract/troubleshooting
```

## Components

### API Deployment
- Image: `.Values.api.image.repository` + `.Values.api.image.tag`. When `tag` is empty (default), template falls back to `.Chart.AppVersion`. `pullPolicy: IfNotPresent`.
- Replicas: 2 (prod), 1 (dev).
- Resources (from issue #28): requests 128Mi/100m, limits 256Mi/500m.
- Env: `TSA_REDIS_URL` built from the Bitnami Redis service name + auth secret; `TSA_SHARED_SECRET` from referenced secret; `TSA_LOG_LEVEL` from ConfigMap.
- Probes: readiness `GET /health` (initialDelay 5s, period 10s); liveness `GET /health` (initialDelay 15s, period 20s).

### API Service
- `ClusterIP`, port 80 → targetPort 8000. No Ingress.

### Redis
- Bitnami `redis` subchart, pinned exact version in `Chart.yaml`.
- `architecture: standalone`, `auth.enabled: true`, password sourced from an externally managed secret.
- Persistence enabled with `storageClass: local-path`, `size: 1Gi` (prod) / `256Mi` (dev).

### CronJobs
Single template iterating `.Values.cronjobs`. Each entry produces one `CronJob` named `<release>-<entry.name>`.

Per-entry shape:
```yaml
- name: saturday-morning
  schedule: "0 7 * * 5"
  image:                       # optional override; defaults to .Values.cli.image
    repository: ghcr.io/stebennett/tee-sniper-cli
    tag: "0.3.1"               # required when image override is set; "latest" rejected by schema
  args:
    - "-b=https://example.com/"
    - "-d=8"
    - "-t=09:00"
    - "-e=11:00"
    - "-s=partner1,partner2"
  env: []                      # extra env vars
  suspend: false
```

CronJob defaults:
- `concurrencyPolicy: Forbid`
- `successfulJobsHistoryLimit: 3`, `failedJobsHistoryLimit: 3`
- `backoffLimit: 2`
- Each pod mounts `cli.existingSecret` as env vars (Twilio creds, booking creds, shared secret) and is wired to call `http://<release>-tee-sniper-api.<namespace>.svc/`.

### NetworkPolicy (opt-in)
Gated by `.Values.networkPolicy.enabled`. When enabled, two policies are rendered:
1. **Redis ingress:** allow port 6379 only from pods labelled `app.kubernetes.io/name=tee-sniper-api` in the same namespace.
2. **API ingress:** allow port 8000 from
   - the chart's own CronJob pods (label `app.kubernetes.io/component=cli`), AND
   - any pod matching a configurable selector `.Values.networkPolicy.apiAllowedClients` (default: `{ matchLabels: { tee-sniper.io/api-client: "true" } }`).

Other in-cluster workloads opt in to API access by adding the configured label to their pods.

## Values surface (top-level)

```yaml
api:
  image:
    repository: ghcr.io/stebennett/tee-sniper-api
    tag: ""                   # empty → use .Chart.AppVersion
    pullPolicy: IfNotPresent
  replicas: 2
  resources:
    requests: { memory: 128Mi, cpu: 100m }
    limits:   { memory: 256Mi, cpu: 500m }
  config:
    logLevel: INFO
  existingSecret: tee-sniper-api    # required keys: shared-secret

cli:
  image:
    repository: ghcr.io/stebennett/tee-sniper-cli
    tag: ""                         # empty → use .Chart.AppVersion
    pullPolicy: IfNotPresent
  existingSecret: tee-sniper-cli    # required keys listed in Secret contract below

cronjobs: []

redis:                              # passed through to bitnami/redis subchart
  enabled: true
  architecture: standalone
  auth:
    enabled: true
    existingSecret: redis-auth
    existingSecretPasswordKey: password
  master:
    persistence:
      enabled: true
      storageClass: local-path
      size: 1Gi

networkPolicy:
  enabled: false
  apiAllowedClients:
    matchLabels:
      tee-sniper.io/api-client: "true"
```

## Secret contract

The chart never creates Secrets. It references three secrets by name; the user provisions them (in practice, via 1Password operator).

| Secret name (default)     | Required keys                                                                                                    | Consumer            |
|---------------------------|------------------------------------------------------------------------------------------------------------------|---------------------|
| `tee-sniper-api`          | `shared-secret`                                                                                                  | API pods            |
| `tee-sniper-cli`          | `username`, `pin`, `twilio-account-sid`, `twilio-auth-token`, `to-number`, `from-number`, `shared-secret`        | CronJob pods        |
| `redis-auth`              | `password`                                                                                                       | Redis + API         |

Names are configurable via `*.existingSecret` values. README documents the exact keys and a `kubectl create secret` fallback.

## Data & runtime flow

```
CronJob fires
  └── pulls tee-sniper-cli image (pinned tag)
      mounts tee-sniper-cli secret as env
      runs: tee-sniper-cli --api-url=http://<release>-tee-sniper-api.<ns>.svc/ <args>
        │
        ▼
   API Service (ClusterIP :80 → :8000)
        │
        ├── reads/writes session in Redis (auth from redis-auth secret)
        └── proxies booking-site interaction
        │
   CLI receives booking result
        │
        └── sends Twilio SMS using its own secret
```

Properties:
- API restarts are safe — sessions live in Redis.
- Redis restart invalidates active sessions; the CLI re-authenticates on next run.
- CronJobs do not retry on 5xx — a missed booking window is missed; retrying minutes later would book the wrong slot.

## Environments

- `values-dev.yaml`: `api.replicas: 1`, smaller Redis persistence, `cronjobs: []`, `networkPolicy.enabled: false`.
- `values-prod.yaml`: `api.replicas: 2`, full resources, real `cronjobs:` entries, `networkPolicy.enabled: true`.

Install / upgrade:
```sh
helm dep update charts/tee-sniper-api
helm upgrade --install tee-sniper charts/tee-sniper-api \
  -n tee-sniper --create-namespace \
  -f charts/tee-sniper-api/values-prod.yaml
```

## Versioning

- `Chart.yaml` `appVersion` is the single source of truth for the app image tag. Bumping `appVersion` upgrades both API and CLI images (they ship from the same repo).
- `Chart.yaml` `version` follows semver for chart changes independent of app version.
- Bitnami Redis pinned to an exact `version:` in the dependencies block; bumps are deliberate.
- `values.schema.json` rejects `tag: "latest"` for both `api.image.tag` and CronJob image overrides.

## Testing & validation

- `helm lint charts/tee-sniper-api` — runs in CI (extends `.github/workflows/build.yml`).
- `helm template charts/tee-sniper-api -f values-prod.yaml | kubeconform -strict -summary` — schema-validates rendered manifests.
- `values.schema.json` enforces required fields and rejects `latest` tags at install time.
- Local smoke test (k3s/kind) documented in chart README.
- `helm unittest` is **not** included initially — `lint + kubeconform + schema` covers regressions for this chart's complexity.

## Error modes & operator UX

| Failure                              | Symptom                                                       | Where to look                            |
|--------------------------------------|---------------------------------------------------------------|------------------------------------------|
| Required Secret missing              | API pod stuck in `CreateContainerConfigError`                 | `kubectl describe pod`; README troubleshooting |
| Redis unreachable                    | API readiness probe fails; Service drops endpoint             | `kubectl logs deploy/<release>-tee-sniper-api` |
| CronJob image pull fails             | Job marked failed after `backoffLimit`                        | `kubectl get jobs -n tee-sniper`         |
| Booking API 5xx during CronJob run   | CronJob exits non-zero; no SMS sent; no automatic retry       | Job logs; manual investigation           |
| Schema validation rejects values     | `helm install` fails immediately                              | `helm install` stderr                    |

## Documentation deliverables

`charts/tee-sniper-api/README.md`:
- Prerequisites (k3s, helm 3.x)
- `helm dep update` step
- Secret contract (table) with `kubectl create secret` examples
- Install/upgrade commands per environment
- Adding a new CronJob schedule (one-line values change)
- Granting another workload access to the API (label opt-in)
- Troubleshooting table

## Acceptance criteria

- `helm lint charts/tee-sniper-api` clean.
- `helm template ... | kubeconform -strict` clean for both `values-dev.yaml` and `values-prod.yaml`.
- `helm upgrade --install` against a local k3s cluster brings API + Redis to Ready.
- A CronJob entry in values renders to a working CronJob that successfully calls the API.
- README walks a fresh operator from zero to a deployed chart.
- CI runs `helm lint` and `kubeconform` on every PR touching `charts/`.
