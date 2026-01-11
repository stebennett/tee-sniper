# tee-sniper Helm Chart

A Helm chart for deploying tee-sniper golf booking automation as a Kubernetes CronJob.

## Overview

This chart deploys tee-sniper as a CronJob that runs on a configurable schedule to automatically book golf tee times. The application:

- Logs into a golf course booking website
- Searches for available tee times within your specified time range
- Books a randomly selected available slot
- Sends SMS confirmation via Twilio

## Prerequisites

- Kubernetes 1.21+
- Helm 3.0+
- Twilio account for SMS notifications
- Golf course booking website credentials

## Installation

### Quick Start

```bash
# Add your credentials via --set flags
helm install tee-sniper ./helm/tee-sniper \
  --namespace tee-sniper \
  --create-namespace \
  --set config.baseUrl="https://your-golf-course.com/" \
  --set secrets.username="your-username" \
  --set secrets.pin="your-pin" \
  --set secrets.fromNumber="+1234567890" \
  --set secrets.toNumber="+0987654321" \
  --set secrets.twilioAccountSid="ACxxxx" \
  --set secrets.twilioAuthToken="your-token"
```

### Using a Values File

```bash
# Create your values file (do not commit secrets!)
cp values.yaml my-values.yaml
# Edit my-values.yaml with your configuration

helm install tee-sniper ./helm/tee-sniper \
  --namespace tee-sniper \
  --create-namespace \
  -f my-values.yaml
```

### With External Secrets

For production deployments, use external secret management:

```bash
# Create secret manually or via External Secrets Operator
kubectl create secret generic tee-sniper-credentials \
  --from-literal=TS_USERNAME='your-username' \
  --from-literal=TS_PIN='your-pin' \
  --from-literal=TS_FROM_NUMBER='+1234567890' \
  --from-literal=TS_TO_NUMBER='+0987654321' \
  --from-literal=TWILIO_ACCOUNT_SID='ACxxxx' \
  --from-literal=TWILIO_AUTH_TOKEN='your-token' \
  -n tee-sniper

# Install chart without creating secrets
helm install tee-sniper ./helm/tee-sniper \
  --namespace tee-sniper \
  --set secrets.create=false \
  --set existingSecret=tee-sniper-credentials \
  --set config.baseUrl="https://your-golf-course.com/"
```

## Configuration

### Image Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.repository` | Container image repository | `ghcr.io/stebennett/tee-sniper` |
| `image.tag` | Container image tag | `latest` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `imagePullSecrets` | Image pull secrets | `[]` |

### Schedule Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `schedule` | Cron expression for job schedule | `0 8 * * 1` (Monday 8AM UTC) |

### Application Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `config.daysAhead` | Days ahead to search for tee time | `7` |
| `config.timeStart` | Earliest booking time (HH:MM) | `14:00` |
| `config.timeEnd` | Latest booking time (HH:MM) | `16:30` |
| `config.baseUrl` | Golf course website base URL | `""` |
| `config.retries` | Number of retry attempts | `5` |
| `config.dryRun` | Dry run mode (no actual booking) | `false` |
| `config.partners` | Comma-separated partner IDs | `""` |

### Secrets Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `secrets.create` | Create Secret resource | `true` |
| `secrets.username` | Booking site username | `""` |
| `secrets.pin` | Booking site PIN | `""` |
| `secrets.fromNumber` | Twilio sender phone number | `""` |
| `secrets.toNumber` | SMS recipient phone number | `""` |
| `secrets.twilioAccountSid` | Twilio account SID | `""` |
| `secrets.twilioAuthToken` | Twilio auth token | `""` |
| `existingSecret` | Name of existing secret (when `secrets.create=false`) | `""` |

### Job Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `job.backoffLimit` | Retries before marking job failed | `1` |
| `job.successfulJobsHistoryLimit` | Successful jobs to keep | `3` |
| `job.failedJobsHistoryLimit` | Failed jobs to keep | `3` |
| `job.startingDeadlineSeconds` | Deadline for starting the job | `300` |
| `job.concurrencyPolicy` | Concurrency policy | `Forbid` |
| `job.ttlSecondsAfterFinished` | TTL after job completion | `86400` |

### Pod Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `pod.restartPolicy` | Pod restart policy | `Never` |
| `pod.annotations` | Pod annotations | `{}` |
| `pod.labels` | Additional pod labels | `{}` |
| `pod.nodeSelector` | Node selector | `{}` |
| `pod.tolerations` | Tolerations | `[]` |
| `pod.affinity` | Affinity rules | `{}` |
| `pod.securityContext` | Pod security context | See values.yaml |

### Resource Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `resources.requests.cpu` | CPU request | Not set |
| `resources.requests.memory` | Memory request | Not set |
| `resources.limits.cpu` | CPU limit | Not set |
| `resources.limits.memory` | Memory limit | Not set |

### Service Account Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `serviceAccount.create` | Create service account | `true` |
| `serviceAccount.annotations` | Service account annotations | `{}` |
| `serviceAccount.name` | Service account name | Auto-generated |

## ArgoCD Deployment

See the `argocd/` directory for example ArgoCD Application manifests.

```bash
# Deploy via ArgoCD
kubectl apply -f argocd/application.yaml -n argocd
```

## Manual Job Trigger

To manually trigger the job for testing:

```bash
# Create a one-off job from the CronJob
kubectl create job --from=cronjob/tee-sniper manual-test -n tee-sniper

# Watch the job
kubectl logs -f job/manual-test -n tee-sniper

# Clean up
kubectl delete job manual-test -n tee-sniper
```

## Dry Run Mode

Test your configuration without making actual bookings:

```bash
helm install tee-sniper ./helm/tee-sniper \
  --namespace tee-sniper \
  --create-namespace \
  --set config.dryRun=true \
  # ... other values
```

## Uninstallation

```bash
helm uninstall tee-sniper -n tee-sniper
kubectl delete namespace tee-sniper
```

## Troubleshooting

### View CronJob Status

```bash
kubectl get cronjobs -n tee-sniper
kubectl describe cronjob tee-sniper -n tee-sniper
```

### View Job History

```bash
kubectl get jobs -n tee-sniper
kubectl logs job/<job-name> -n tee-sniper
```

### Check Secret Configuration

```bash
kubectl get secret -n tee-sniper
kubectl describe secret tee-sniper -n tee-sniper
```
