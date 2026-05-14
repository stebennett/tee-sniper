# tee-sniper-api Helm chart

Deploys the tee-sniper FastAPI service plus Redis to a Kubernetes cluster, and runs `tee-sniper-cli` as a configurable list of CronJobs.

## Prerequisites

- Kubernetes 1.27+ (tested on k3s)
- Helm 3.14+ (also works on Helm 4.x)
- A storage class for Redis persistence (k3s default: `local-path`)
- The Bitnami chart repository: `helm repo add bitnami https://charts.bitnami.com/bitnami`
- Required Secrets created in the target namespace (see below)

## Secret contract

The chart never creates Secrets. Three Secrets must exist before installing:

| Secret (default name) | Required keys                                                                                                          |
|-----------------------|------------------------------------------------------------------------------------------------------------------------|
| `tee-sniper-api`      | `shared-secret`                                                                                                        |
| `tee-sniper-cli`      | `username`, `pin`, `twilio-account-sid`, `twilio-auth-token`, `to-number`, `from-number`, `shared-secret`              |
| `redis-auth`          | `password`                                                                                                             |

Names are configurable via `api.existingSecret`, `cli.existingSecret`, `redis.auth.existingSecret`.

CLI secret keys are mounted into the CronJob pods as env vars matching the Go CLI's `TS_*` convention (`TS_USERNAME`, `TS_PIN`, `TS_TO_NUMBER`, `TS_FROM_NUMBER`, `TS_SHARED_SECRET`) plus `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` for the Twilio SDK.

Manual creation example (typically the 1Password operator handles this):
```sh
kubectl -n tee-sniper create secret generic tee-sniper-api --from-literal=shared-secret=...
kubectl -n tee-sniper create secret generic tee-sniper-cli \
  --from-literal=username=... \
  --from-literal=pin=... \
  --from-literal=twilio-account-sid=... \
  --from-literal=twilio-auth-token=... \
  --from-literal=to-number=... \
  --from-literal=from-number=... \
  --from-literal=shared-secret=...
kubectl -n tee-sniper create secret generic redis-auth --from-literal=password=...
```

## Required runtime config

The API also requires the booking-site base URL. Set it in your values file:

```yaml
api:
  config:
    baseUrl: "https://your-booking-site.example.com/"
```

If `baseUrl` is empty, the API pod will crash on startup (the install renders, but pods CrashLoop). The chart's `NOTES.txt` warns when this is empty.

## Install

```sh
helm dep update charts/tee-sniper-api
kubectl create namespace tee-sniper
# Create secrets per the table above
helm upgrade --install tee-sniper charts/tee-sniper-api \
  -n tee-sniper \
  -f charts/tee-sniper-api/values-prod.yaml
```

## Upgrade

Application image versions are driven by `appVersion` in `Chart.yaml`. To bump:

1. Edit `Chart.yaml` and set `appVersion: "X.Y.Z"`.
2. Bump chart `version:` (semver — patch for value-only changes, minor for template changes).
3. `helm dep update charts/tee-sniper-api` (only if dependencies changed).
4. `helm upgrade tee-sniper charts/tee-sniper-api -n tee-sniper -f charts/tee-sniper-api/values-prod.yaml`.

To pin a different image tag without changing `appVersion`, set `api.image.tag` and/or `cli.image.tag` in your values file. The schema rejects any case-variant of `latest`.

## Adding a new scheduled booking

Append an entry to `cronjobs:` in your values file:

```yaml
cronjobs:
  - name: friday-evening
    schedule: "0 7 * * 4"
    args:
      - "-b=https://golf.example.com/"
      - "-d=8"
      - "-t=17:00"
      - "-e=19:00"
      - "-s=partner1,partner2"
```

`name` must be DNS-label-compliant (lowercase, digits, hyphens) and at most 40 characters. Re-run `helm upgrade` to apply.

The chart automatically appends `--api-url=http://<release>-tee-sniper-api...` to the args list as the LAST argument. Because go-flags resolves duplicate flags to the last value, an operator-supplied `--api-url` in `args:` will be silently overridden by the chart's value — this is intentional and prevents accidental misrouting.

## Granting another in-cluster workload access to the API

The API is `ClusterIP` only. With `networkPolicy.enabled: true`, only the chart's own CronJobs can reach it by default. Other workloads opt in by labelling their pods to match `networkPolicy.apiAllowedClients`:

```yaml
# In another workload's pod spec
metadata:
  labels:
    tee-sniper.io/api-client: "true"
```

Or override the selector in your values file:

```yaml
networkPolicy:
  apiAllowedClients:
    matchLabels:
      team: platform
      tee-sniper.io/api-client: "true"   # keep this if you want CronJobs from other releases too
```

> **Note on Helm merge behaviour:** When you override `networkPolicy.apiAllowedClients` in a values file, Helm performs a deep merge with the chart default. To fully replace the selector, list every label you want explicitly. Setting `--set networkPolicy.apiAllowedClients.matchLabels.team=platform` will MERGE `team: platform` into the default selector, not replace it.

## Production considerations

- The CronJob containers ship without `resources:` requests/limits. For shared clusters, set per-cronjob resource bounds in your values overrides to prevent unbounded resource consumption from a hung run.
- The Bitnami Redis subchart's own NetworkPolicy is disabled by this chart (`redis.networkPolicy.enabled: false` in `values.yaml`). Our `templates/networkpolicy.yaml` owns Redis traffic policy. Do not re-enable Bitnami's policy without disabling ours, or you will end up with overlapping rules that nullify the access restrictions (Kubernetes unions NetworkPolicy `from:` clauses).

## Troubleshooting

| Symptom                                         | Diagnosis                                                                                  |
|-------------------------------------------------|--------------------------------------------------------------------------------------------|
| API pod stuck in `CreateContainerConfigError`   | A referenced Secret is missing. `kubectl -n tee-sniper describe pod <name>` shows which.   |
| API pod CrashLoopBackOff at startup             | Likely `api.config.baseUrl` is empty. Set it in your values file and re-upgrade.           |
| API readiness probe failing                     | Redis unreachable or wrong password. `kubectl logs deploy/tee-sniper-tee-sniper-api`.      |
| `helm install` fails with schema error          | Check `tag` is not `"latest"` (case-insensitive) and `logLevel` is one of DEBUG/INFO/WARNING/ERROR/CRITICAL. |
| CronJob runs but exits non-zero                 | API call failed. `kubectl logs job/<jobname> -n tee-sniper`. No automatic retry — by design.|
| Other in-cluster service can't reach API        | Add the `networkPolicy.apiAllowedClients` label to its pods, or merge a new selector.       |
| CronJob name rejected by schema                 | Names must be DNS-label-compliant (lowercase + digits + hyphens) and ≤ 40 characters.       |

## Local smoke test (k3s/kind)

```sh
# kind cluster
kind create cluster
helm dep update charts/tee-sniper-api
kubectl create namespace tee-sniper
kubectl -n tee-sniper create secret generic tee-sniper-api --from-literal=shared-secret=test
kubectl -n tee-sniper create secret generic tee-sniper-cli \
  --from-literal=username=u --from-literal=pin=p \
  --from-literal=twilio-account-sid=AC --from-literal=twilio-auth-token=t \
  --from-literal=to-number=+1 --from-literal=from-number=+1 \
  --from-literal=shared-secret=test
kubectl -n tee-sniper create secret generic redis-auth --from-literal=password=devpass
helm install tee-sniper charts/tee-sniper-api -n tee-sniper \
  -f charts/tee-sniper-api/values-dev.yaml \
  --set api.config.baseUrl=https://example.com/ \
  --set redis.master.persistence.storageClass=standard
kubectl -n tee-sniper get pods -w
```
