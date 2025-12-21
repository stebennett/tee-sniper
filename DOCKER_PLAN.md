# Docker Deployment Plan for Tee-Sniper

This document outlines the plan for containerizing Tee-Sniper.

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

## Phase 1: Docker Implementation ✅

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
FROM alpine:3.21

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

### 1.3 Configuration for Container Operation

- Pass arguments via Docker run command
- Environment variables for secrets (Twilio credentials)

---

## Phase 2: Configuration Refactoring ✅

To make the application more container-friendly, refactor `pkg/config/config.go` to support environment variables as fallbacks:

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

## Phase 3: CI/CD Pipeline Updates ✅

### 3.1 Add Docker Build to GitHub Actions

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

## Implementation Phases Summary

| Phase | Description | Files to Create/Modify |
|-------|-------------|----------------------|
| 1 | Docker basics | `Dockerfile`, `.dockerignore` |
| 2 | Config refactor | `pkg/config/config.go` (add env tag support) |
| 3 | CI/CD update | `.github/workflows/docker.yml` |

---

## Key Decisions Needed

1. **Container Registry**: GitHub Container Registry (GHCR), Docker Hub, or private registry?

---

## Next Steps

- [x] Phase 1: Create Dockerfile and .dockerignore
- [x] Phase 1: Test local Docker build
- [x] Phase 2: Refactor config.go for env var support
- [x] Phase 3: Update CI/CD workflows
