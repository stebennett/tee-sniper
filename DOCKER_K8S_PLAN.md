# Docker & Kubernetes Deployment Plan for Tee-Sniper

This document outlines the comprehensive plan for containerizing Tee-Sniper and deploying it to Kubernetes.

## Current Application Analysis

### How the Application Accesses the Booking Website

The `BookingClient` (`pkg/clients/bookingclient.go`) handles all website interactions:

1. **Session Management**: Uses `net/http/cookiejar` for automatic cookie persistence across requests
2. **Authentication**: Form-based POST to `{baseUrl}login.php` with username/PIN
3. **Anti-Detection Features**:
   - Random user-agent selection from 5 browser profiles
   - Browser-like HTTP headers (Accept, Accept-Language, etc.)
   - Retry logic with jitter (5-15 second delays)
4. **HTML Parsing**: Uses `goquery` to scrape availability tables and extract form data
5. **Network Requirements**: Standard HTTPS egress only - no special ports or protocols

### Key Characteristics for Containerization

- **Stateless**: No database, no file persistence, no local state
- **Batch Job**: Single execution, not a long-running service
- **External Dependencies**: Golf course website (HTTP), Twilio API (HTTPS)
- **Configuration**: CLI flags + environment variables

---

## Phase 1: Docker Implementation

### 1.1 Create Multi-Stage Dockerfile

```dockerfile
# Build stage
FROM golang:1.25-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o tee-sniper cmd/tee-sniper/main.go

# Runtime stage
FROM alpine:3.19

RUN apk --no-cache add ca-certificates tzdata
WORKDIR /app
COPY --from=builder /app/tee-sniper .

ENTRYPOINT ["/app/tee-sniper"]
```

**Rationale:**
- Multi-stage build reduces image size (~15MB vs ~800MB)
- Alpine base for minimal attack surface
- `ca-certificates` required for HTTPS to booking site and Twilio
- `tzdata` for proper timezone handling (important for booking times)
- CGO disabled for fully static binary

### 1.2 Create .dockerignore

```
.git
.env
.env.example
*.md
testdata/
vendor/
.github/
```

### 1.3 Update Configuration for Container-Friendly Operation

**Option A: Keep CLI flags (Recommended for flexibility)**
- Pass arguments via K8s command/args or Docker run
- Environment variables for secrets only (Twilio)

**Option B: Full environment variable support**
- Add environment variable fallbacks in `pkg/config/config.go`
- More K8s native but requires code changes

---

## Phase 2: Kubernetes Deployment

### 2.1 Deployment Model: CronJob

Since Tee-Sniper is a batch job that runs once and exits, K8s **CronJob** is the ideal primitive:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: tee-sniper
  namespace: tee-sniper
spec:
  schedule: "0 6 * * *"  # Run daily at 6 AM
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 5
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        spec:
          restartPolicy: Never
          containers:
          - name: tee-sniper
            image: your-registry/tee-sniper:latest
            args:
            - "-d"
            - "7"
            - "-t"
            - "15:00"
            - "-e"
            - "17:00"
            - "-r"
            - "5"
            envFrom:
            - secretRef:
                name: tee-sniper-secrets
            - configMapRef:
                name: tee-sniper-config
```

### 2.2 Secrets Management

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: tee-sniper-secrets
  namespace: tee-sniper
type: Opaque
stringData:
  TWILIO_ACCOUNT_SID: "your-sid"
  TWILIO_AUTH_TOKEN: "your-token"
  TS_PIN: "your-pin"  # Sensitive credential
```

### 2.3 ConfigMap for Non-Sensitive Config

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: tee-sniper-config
  namespace: tee-sniper
data:
  TS_USERNAME: "your-username"
  TS_BASEURL: "https://your-golf-course.com/"
  TS_FROM_NUMBER: "+1234567890"
  TS_TO_NUMBER: "+0987654321"
```

### 2.4 Namespace and RBAC

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tee-sniper
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: tee-sniper
  namespace: tee-sniper
```

---

## Phase 3: Configuration Refactoring

To make the application more K8s-native, refactor `pkg/config/config.go` to support environment variables as fallbacks:

```go
type Config struct {
    DaysAhead   int    `short:"d" long:"days" env:"TS_DAYS_AHEAD" required:"true"`
    TimeStart   string `short:"t" long:"timestart" env:"TS_TIME_START" required:"true"`
    TimeEnd     string `short:"e" long:"timeend" env:"TS_TIME_END" required:"true"`
    // ... etc
}
```

The `go-flags` library already supports `env` tags, so this is a minimal change.

---

## Phase 4: CI/CD Pipeline Updates

### 4.1 Add Docker Build to GitHub Actions

```yaml
# .github/workflows/docker.yml
name: Docker Build

on:
  push:
    tags: ['v*.*.*']
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Build Docker image
      run: docker build -t tee-sniper:${{ github.sha }} .

    - name: Run tests in container
      run: docker run --rm tee-sniper:${{ github.sha }} -h

    - name: Push to registry
      if: startsWith(github.ref, 'refs/tags/')
      run: |
        docker tag tee-sniper:${{ github.sha }} ghcr.io/${{ github.repository }}:${{ github.ref_name }}
        docker push ghcr.io/${{ github.repository }}:${{ github.ref_name }}
```

---

## Phase 5: Operational Considerations

### 5.1 Logging

- **Current**: Uses `log` package with stdout
- **For K8s**: This is ideal - logs go to container stdout, collected by K8s logging
- **Consider**: Adding structured logging (JSON) for better log aggregation

### 5.2 Monitoring

- **Job Success/Failure**: K8s tracks job completion status
- **SMS Delivery**: Twilio provides delivery receipts
- **Prometheus Metrics**: Optional - add metrics endpoint for retry counts, booking success rate

### 5.3 Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tee-sniper-egress
  namespace: tee-sniper
spec:
  podSelector:
    matchLabels:
      app: tee-sniper
  policyTypes:
  - Egress
  egress:
  - to: []  # Allow all egress (golf site, Twilio API)
    ports:
    - protocol: TCP
      port: 443
```

### 5.4 Resource Limits

```yaml
resources:
  requests:
    memory: "64Mi"
    cpu: "50m"
  limits:
    memory: "128Mi"
    cpu: "200m"
```

---

## Implementation Phases Summary

| Phase | Description | Files to Create/Modify |
|-------|-------------|----------------------|
| 1 | Docker basics | `Dockerfile`, `.dockerignore` |
| 2 | K8s manifests | `k8s/cronjob.yaml`, `k8s/secrets.yaml`, `k8s/configmap.yaml` |
| 3 | Config refactor | `pkg/config/config.go` (add env tag support) |
| 4 | CI/CD update | `.github/workflows/docker.yml` |
| 5 | Ops enhancements | Network policies, resource limits, monitoring |

---

## Key Decisions Needed

1. **Container Registry**: GitHub Container Registry (GHCR), Docker Hub, or private registry?
2. **Scheduling Strategy**: Single daily CronJob or multiple jobs for different time windows?
3. **Environment Variables vs CLI Args**: Full env var support or keep CLI args with K8s `args`?
4. **Secrets Management**: K8s Secrets, External Secrets Operator, or Vault?

---

## Next Steps

- [ ] Phase 1: Create Dockerfile and .dockerignore
- [ ] Phase 1: Test local Docker build
- [ ] Phase 2: Create K8s manifest files
- [ ] Phase 3: Refactor config.go for env var support
- [ ] Phase 4: Update CI/CD workflows
- [ ] Phase 5: Add operational enhancements
