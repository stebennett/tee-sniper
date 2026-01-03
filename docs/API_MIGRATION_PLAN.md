# API Migration Plan

This document outlines the plan to split tee-sniper into two applications:
1. **tee-sniper-api** - Python FastAPI service for website interaction
2. **tee-sniper-cli** - Modified Go CLI that calls the API

## GitHub Issues

**Epic:** #30 - API Architecture Migration

| Phase | Issue | Description |
|-------|-------|-------------|
| 1 | #22 | API Foundation - Python FastAPI Project Setup |
| 2 | #23 | Redis Integration - Session Management |
| 3 | #24 | Booking Client - Website Interaction Logic |
| 4 | #25 | API Endpoints - REST Interface Implementation |
| 5 | #26 | Docker Configuration - Containerization |
| 6 | #27 | Go CLI Updates - API Client Integration |
| 7 | #28 | Kubernetes Deployment - Production Infrastructure |
| 8 | #29 | CI/CD Pipeline - Automated Build and Deploy |

## Architecture Overview

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│                     │     │                     │     │                     │
│   tee-sniper-cli    │────▶│   tee-sniper-api    │────▶│   Golf Course Site  │
│   (Go CLI App)      │     │   (FastAPI + Redis) │     │   (External)        │
│                     │     │                     │     │                     │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
        │                           │
        │                           ▼
        │                   ┌─────────────────────┐
        │                   │                     │
        │                   │       Redis         │
        │                   │   (Session Store)   │
        │                   │                     │
        │                   └─────────────────────┘
        │
        ▼
┌─────────────────────┐
│                     │
│       Twilio        │
│   (SMS Notifications)│
│                     │
└─────────────────────┘
```

## Phase 1: Python FastAPI Service

### 1.1 Project Structure

```
api/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Settings/configuration
│   ├── dependencies.py         # Dependency injection
│   ├── models/
│   │   ├── __init__.py
│   │   ├── requests.py         # Pydantic request models
│   │   ├── responses.py        # Pydantic response models
│   │   └── domain.py           # Domain models (TimeSlot, etc.)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py             # /api/login endpoint
│   │   ├── teetimes.py         # /api/{date}/times endpoint
│   │   └── bookings.py         # Booking and partner endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── booking_client.py   # Website interaction logic
│   │   ├── session_manager.py  # Redis session management
│   │   └── encryption.py       # Shared secret encryption
│   └── utils/
│       ├── __init__.py
│       ├── user_agents.py      # User agent rotation
│       └── html_parser.py      # BeautifulSoup parsing helpers
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_teetimes.py
│   └── test_bookings.py
├── Dockerfile
├── requirements.txt
├── pyproject.toml
└── README.md
```

### 1.2 API Endpoints

#### POST /api/login
Authenticates user and returns access token.

**Request:**
```json
{
  "credentials": "<encrypted_username:pin>",
  "base_url": "https://example.com/"
}
```

The `credentials` field contains `username:pin` encrypted with AES-256-GCM using a shared secret.

**Response (200):**
```json
{
  "access_token": "uuid-token-here",
  "expires_at": "2024-01-15T10:30:00Z"
}
```

**Response (401):**
```json
{
  "detail": "Login failed: invalid credentials"
}
```

**Implementation Notes:**
- Decrypt credentials using shared secret (from environment variable)
- Perform login to golf course website
- Store cookies in Redis with generated UUID token as key
- Set TTL of 30 minutes on Redis key
- Return token to client

---

#### GET /api/{date}/times
Retrieves available tee times for a given date.

**Path Parameters:**
- `date`: Date in `YYYY-MM-DD` format

**Query Parameters:**
- `start` (optional): Start time filter in `HH:MM` format
- `end` (optional): End time filter in `HH:MM` format

**Headers:**
- `Authorization: Bearer <access_token>`

**Response (200):**
```json
{
  "date": "2024-01-15",
  "times": [
    {
      "time": "09:00",
      "can_book": true,
      "booking_form": {
        "date": "15-01-2024",
        "time": "0900",
        "course": "1",
        "holes": "18"
      }
    },
    {
      "time": "09:10",
      "can_book": true,
      "booking_form": { ... }
    }
  ],
  "filtered_count": 5,
  "total_count": 12
}
```

**Response (401):**
```json
{
  "detail": "Invalid or expired access token"
}
```

**Implementation Notes:**
- Retrieve cookies from Redis using token
- Convert date from `YYYY-MM-DD` to `DD-MM-YYYY` for website
- Parse HTML response using BeautifulSoup
- Apply time filters if provided
- Return filtered list

---

#### POST /api/{date}/time/{time}/book
Books a tee time.

**Path Parameters:**
- `date`: Date in `YYYY-MM-DD` format
- `time`: Time in `HH:MM` format (URL encoded, so `09:00` becomes `09%3A00`)

**Headers:**
- `Authorization: Bearer <access_token>`

**Request Body:**
```json
{
  "num_slots": 2,
  "dry_run": false
}
```

**Response (200):**
```json
{
  "booking_id": "BOOK123456",
  "date": "2024-01-15",
  "time": "09:00",
  "slots_booked": 2,
  "message": "Successfully booked tee time"
}
```

**Response (400):**
```json
{
  "detail": "Time slot not available or already booked"
}
```

**Response (404):**
```json
{
  "detail": "Time slot not found for specified date/time"
}
```

**Implementation Notes:**
- First fetch availability to get booking form parameters
- Find the matching time slot
- Submit booking request with `numslots` parameter
- Extract booking ID from redirect URL
- Return booking confirmation

---

#### PATCH /api/bookings/{booking_id}
Adds playing partners to an existing booking.

**Path Parameters:**
- `booking_id`: The booking ID returned from the book endpoint

**Headers:**
- `Authorization: Bearer <access_token>`

**Request Body:**
```json
{
  "partners": ["partner1_id", "partner2_id"],
  "dry_run": false
}
```

**Response (200):**
```json
{
  "booking_id": "BOOK123456",
  "partners_added": ["partner1_id", "partner2_id"],
  "message": "Partners added successfully"
}
```

**Response (207 - Partial Success):**
```json
{
  "booking_id": "BOOK123456",
  "partners_added": ["partner1_id"],
  "partners_failed": ["partner2_id"],
  "message": "Some partners could not be added"
}
```

**Implementation Notes:**
- Loop through partners list
- Call `addpartner` endpoint for each with incrementing slot numbers (2, 3, 4...)
- Return success/partial success based on results

---

### 1.3 Core Services

#### Session Manager (session_manager.py)
```python
class SessionManager:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.ttl = 1800  # 30 minutes

    async def store_session(self, cookies: dict, base_url: str) -> str:
        """Store cookies and return access token."""
        token = str(uuid.uuid4())
        session_data = {
            "cookies": cookies,
            "base_url": base_url,
            "created_at": datetime.utcnow().isoformat()
        }
        await self.redis.setex(f"session:{token}", self.ttl, json.dumps(session_data))
        return token

    async def get_session(self, token: str) -> Optional[dict]:
        """Retrieve session data by token."""
        data = await self.redis.get(f"session:{token}")
        if data:
            await self.redis.expire(f"session:{token}", self.ttl)  # Refresh TTL
            return json.loads(data)
        return None

    async def delete_session(self, token: str) -> bool:
        """Delete session (logout)."""
        return await self.redis.delete(f"session:{token}") > 0
```

#### Encryption Service (encryption.py)
```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
import os

class EncryptionService:
    def __init__(self, shared_secret: str):
        # Derive 256-bit key from secret
        self.key = hashlib.sha256(shared_secret.encode()).digest()
        self.aesgcm = AESGCM(self.key)

    def decrypt_credentials(self, encrypted_data: str) -> tuple[str, str]:
        """Decrypt and return (username, pin)."""
        raw = base64.b64decode(encrypted_data)
        nonce = raw[:12]
        ciphertext = raw[12:]
        plaintext = self.aesgcm.decrypt(nonce, ciphertext, None)
        username, pin = plaintext.decode().split(":", 1)
        return username, pin
```

#### Booking Client (booking_client.py)
```python
class BookingClient:
    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36...",
        # ... other user agents from Go implementation
    ]

    def __init__(self, base_url: str, cookies: Optional[dict] = None):
        self.base_url = base_url.rstrip("/")
        self.session = httpx.AsyncClient()
        self.session.headers.update({
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        if cookies:
            self.session.cookies.update(cookies)

    async def login(self, username: str, pin: str) -> bool:
        """Login and return success status."""
        # Implementation mirrors Go version

    async def get_availability(self, date: str) -> list[TimeSlot]:
        """Get available tee times for date (DD-MM-YYYY format)."""
        # Implementation mirrors Go version using BeautifulSoup

    async def book_time_slot(self, time_slot: TimeSlot, num_slots: int) -> str:
        """Book time slot and return booking ID."""
        # Implementation mirrors Go version

    async def add_partner(self, booking_id: str, partner_id: str, slot_num: int) -> bool:
        """Add playing partner to booking."""
        # Implementation mirrors Go version

    def get_cookies(self) -> dict:
        """Return current session cookies for storage."""
        return dict(self.session.cookies)
```

### 1.4 Configuration

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    session_ttl: int = 1800  # 30 minutes

    # Security
    shared_secret: str  # Required - for credential encryption

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json or text

    class Config:
        env_prefix = "TSA_"  # Tee Sniper API
        env_file = ".env"
```

### 1.5 Dependencies

```txt
# requirements.txt
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
httpx>=0.26.0
redis>=5.0.0
beautifulsoup4>=4.12.0
lxml>=5.1.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
cryptography>=42.0.0
python-json-logger>=2.0.0
pytest>=7.4.0
pytest-asyncio>=0.23.0
httpx-mock>=0.30.0
```

---

## Phase 2: Docker Configuration

### 2.1 API Dockerfile

```dockerfile
# api/Dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY app/ ./app/

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2.2 Docker Compose (Local Development)

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build:
      context: ./api
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - TSA_REDIS_URL=redis://redis:6379/0
      - TSA_SHARED_SECRET=${TSA_SHARED_SECRET}
      - TSA_DEBUG=true
      - TSA_LOG_LEVEL=DEBUG
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    command: redis-server --appendonly yes

volumes:
  redis_data:
```

### 2.3 Development Docker Compose Override

```yaml
# docker-compose.override.yml
version: '3.8'

services:
  api:
    build:
      context: ./api
      dockerfile: Dockerfile.dev
    volumes:
      - ./api/app:/app/app:ro
    environment:
      - TSA_DEBUG=true
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Phase 3: Go CLI Modifications

### 3.1 New API Client

```go
// pkg/clients/apiclient.go
package clients

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
    "time"
)

type APIClient struct {
    baseURL     string
    accessToken string
    httpClient  *http.Client
    sharedSecret string
}

type LoginRequest struct {
    Credentials string `json:"credentials"`
    BaseURL     string `json:"base_url"`
}

type LoginResponse struct {
    AccessToken string `json:"access_token"`
    ExpiresAt   string `json:"expires_at"`
}

type TimeSlotResponse struct {
    Time        string            `json:"time"`
    CanBook     bool              `json:"can_book"`
    BookingForm map[string]string `json:"booking_form"`
}

type AvailabilityResponse struct {
    Date          string             `json:"date"`
    Times         []TimeSlotResponse `json:"times"`
    FilteredCount int                `json:"filtered_count"`
    TotalCount    int                `json:"total_count"`
}

type BookRequest struct {
    NumSlots int  `json:"num_slots"`
    DryRun   bool `json:"dry_run"`
}

type BookResponse struct {
    BookingID    string `json:"booking_id"`
    Date         string `json:"date"`
    Time         string `json:"time"`
    SlotsBooked  int    `json:"slots_booked"`
    Message      string `json:"message"`
}

type AddPartnersRequest struct {
    Partners []string `json:"partners"`
    DryRun   bool     `json:"dry_run"`
}

func NewAPIClient(apiBaseURL, sharedSecret string) *APIClient {
    return &APIClient{
        baseURL:      apiBaseURL,
        sharedSecret: sharedSecret,
        httpClient: &http.Client{
            Timeout: 30 * time.Second,
        },
    }
}

func (c *APIClient) Login(username, pin, golfSiteURL string) error {
    // Encrypt credentials
    encrypted := encryptCredentials(username, pin, c.sharedSecret)

    reqBody := LoginRequest{
        Credentials: encrypted,
        BaseURL:     golfSiteURL,
    }

    resp, err := c.doRequest("POST", "/api/login", reqBody, false)
    if err != nil {
        return err
    }

    var loginResp LoginResponse
    if err := json.Unmarshal(resp, &loginResp); err != nil {
        return err
    }

    c.accessToken = loginResp.AccessToken
    return nil
}

func (c *APIClient) GetAvailability(date string, startTime, endTime string) ([]models.TimeSlot, error) {
    url := fmt.Sprintf("/api/%s/times", date)
    if startTime != "" || endTime != "" {
        url += "?"
        if startTime != "" {
            url += "start=" + startTime
        }
        if endTime != "" {
            if startTime != "" {
                url += "&"
            }
            url += "end=" + endTime
        }
    }

    resp, err := c.doRequest("GET", url, nil, true)
    if err != nil {
        return nil, err
    }

    var availResp AvailabilityResponse
    if err := json.Unmarshal(resp, &availResp); err != nil {
        return nil, err
    }

    // Convert to domain model
    slots := make([]models.TimeSlot, len(availResp.Times))
    for i, t := range availResp.Times {
        slots[i] = models.TimeSlot{
            Time:        t.Time,
            CanBook:     t.CanBook,
            BookingForm: t.BookingForm,
        }
    }
    return slots, nil
}

func (c *APIClient) BookTimeSlot(date, time string, numSlots int, dryRun bool) (string, error) {
    url := fmt.Sprintf("/api/%s/time/%s/book", date, time)
    reqBody := BookRequest{
        NumSlots: numSlots,
        DryRun:   dryRun,
    }

    resp, err := c.doRequest("POST", url, reqBody, true)
    if err != nil {
        return "", err
    }

    var bookResp BookResponse
    if err := json.Unmarshal(resp, &bookResp); err != nil {
        return "", err
    }

    return bookResp.BookingID, nil
}

func (c *APIClient) AddPartners(bookingID string, partners []string, dryRun bool) error {
    url := fmt.Sprintf("/api/bookings/%s", bookingID)
    reqBody := AddPartnersRequest{
        Partners: partners,
        DryRun:   dryRun,
    }

    _, err := c.doRequest("PATCH", url, reqBody, true)
    return err
}
```

### 3.2 Configuration Updates

```go
// pkg/config/config.go - additions
type Config struct {
    // Existing fields...

    // API Mode (new)
    APIBaseURL   string `long:"api-url" env:"TS_API_URL" description:"API base URL (enables API mode)"`
    SharedSecret string `long:"shared-secret" env:"TS_SHARED_SECRET" description:"Shared secret for API auth"`

    // Renamed for clarity
    GolfSiteURL  string `short:"b" long:"base-url" env:"TS_BASEURL" description:"Golf course booking site URL"`
}

func (c *Config) UseAPIMode() bool {
    return c.APIBaseURL != ""
}
```

### 3.3 Main Application Updates

```go
// cmd/tee-sniper/main.go - modified Run method
func (a *App) Run() error {
    var client BookingService

    if a.Config.UseAPIMode() {
        // Use API client
        apiClient := clients.NewAPIClient(a.Config.APIBaseURL, a.Config.SharedSecret)
        if err := apiClient.Login(a.Config.Username, a.Config.Pin, a.Config.GolfSiteURL); err != nil {
            return fmt.Errorf("API login failed: %w", err)
        }
        client = apiClient
    } else {
        // Use direct booking client (existing behavior)
        client = a.BookingClient
        if !client.Login(a.Config.Username, a.Config.Pin) {
            return errors.New("login failed")
        }
    }

    // Rest of the flow remains the same...
}
```

---

## Phase 4: Kubernetes Deployment

### 4.1 API Deployment

```yaml
# k8s/api/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tee-sniper-api
  labels:
    app: tee-sniper-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: tee-sniper-api
  template:
    metadata:
      labels:
        app: tee-sniper-api
    spec:
      containers:
        - name: api
          image: ghcr.io/yourusername/tee-sniper-api:latest
          ports:
            - containerPort: 8000
          env:
            - name: TSA_REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: tee-sniper-secrets
                  key: redis-url
            - name: TSA_SHARED_SECRET
              valueFrom:
                secretKeyRef:
                  name: tee-sniper-secrets
                  key: shared-secret
            - name: TSA_LOG_LEVEL
              value: "INFO"
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "500m"
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 20
```

### 4.2 API Service

```yaml
# k8s/api/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: tee-sniper-api
spec:
  selector:
    app: tee-sniper-api
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: ClusterIP
```

### 4.3 Redis Deployment (or use managed Redis)

```yaml
# k8s/redis/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          resources:
            requests:
              memory: "64Mi"
              cpu: "50m"
            limits:
              memory: "128Mi"
              cpu: "100m"
          volumeMounts:
            - name: redis-data
              mountPath: /data
      volumes:
        - name: redis-data
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  selector:
    app: redis
  ports:
    - port: 6379
      targetPort: 6379
```

### 4.4 Secrets

```yaml
# k8s/secrets.yaml (template - don't commit actual values)
apiVersion: v1
kind: Secret
metadata:
  name: tee-sniper-secrets
type: Opaque
stringData:
  redis-url: "redis://redis:6379/0"
  shared-secret: "your-shared-secret-here"
```

---

## Phase 5: Implementation Tasks

### Phase 5.1: API Foundation
- [ ] Create `api/` directory structure
- [ ] Set up pyproject.toml and requirements.txt
- [ ] Implement config.py with pydantic-settings
- [ ] Create FastAPI app skeleton with health endpoint
- [ ] Implement encryption service
- [ ] Write unit tests for encryption

### Phase 5.2: Redis Integration
- [ ] Implement session manager
- [ ] Add Redis connection handling
- [ ] Write session manager tests
- [ ] Add session cleanup/expiry handling

### Phase 5.3: Booking Client
- [ ] Port user agent rotation logic
- [ ] Implement login functionality
- [ ] Implement availability scraping with BeautifulSoup
- [ ] Implement booking logic
- [ ] Implement partner addition
- [ ] Port test fixtures from Go tests
- [ ] Write comprehensive tests

### Phase 5.4: API Endpoints
- [ ] Implement `/api/login` endpoint
- [ ] Implement `/api/{date}/times` endpoint
- [ ] Implement `/api/{date}/time/{time}/book` endpoint
- [ ] Implement `/api/bookings/{booking_id}` PATCH endpoint
- [ ] Add `/health` endpoint
- [ ] Add OpenAPI documentation
- [ ] Write integration tests

### Phase 5.5: Docker Configuration
- [ ] Create API Dockerfile
- [ ] Create docker-compose.yml
- [ ] Create docker-compose.override.yml for dev
- [ ] Test local development workflow
- [ ] Document Docker usage

### Phase 5.6: Go CLI Updates
- [ ] Add encryption helper for credentials
- [ ] Implement APIClient
- [ ] Update config for API mode
- [ ] Update main.go for conditional client selection
- [ ] Maintain backward compatibility with direct mode
- [ ] Update tests

### Phase 5.7: Kubernetes
- [ ] Create API deployment manifest
- [ ] Create API service manifest
- [ ] Create Redis deployment (or configure managed Redis)
- [ ] Create secrets template
- [ ] Create Ingress/NetworkPolicy as needed
- [ ] Document deployment process

### Phase 5.8: CI/CD
- [ ] Add GitHub Action for API Docker build
- [ ] Add API test workflow
- [ ] Add container registry push
- [ ] Update existing Go workflows if needed

---

## Security Considerations

1. **Shared Secret Management**
   - Use Kubernetes secrets or external secret manager
   - Rotate secrets periodically
   - Never log decrypted credentials

2. **API Authentication**
   - Tokens are UUID v4 (122 bits of randomness)
   - 30-minute expiry with sliding window
   - Rate limiting should be considered

3. **Redis Security**
   - Use Redis AUTH in production
   - Network isolation via Kubernetes NetworkPolicy
   - Consider Redis TLS

4. **Credential Handling**
   - AES-256-GCM provides authenticated encryption
   - Nonce is unique per encryption (prepended to ciphertext)
   - Credentials only decrypted at API layer

---

## Testing Strategy

### API Tests
- Unit tests for all services
- Integration tests for endpoints (using httpx-mock)
- HTML parsing tests using Go test fixtures

### CLI Tests
- Unit tests for API client
- Mock API responses for integration tests
- Maintain existing tests for direct mode

### E2E Tests
- Docker Compose based E2E tests
- Test full flow: login → availability → book → add partners

---

## Migration Path

1. **Phase A: Deploy API alongside existing CLI**
   - API is deployed but not used by production CLI
   - Test API independently

2. **Phase B: CLI with feature flag**
   - Add `--api-url` flag to CLI
   - Test API mode in staging

3. **Phase C: Full migration**
   - Default to API mode when `TS_API_URL` is set
   - Document new deployment model

4. **Phase D: Deprecate direct mode (optional)**
   - Remove direct booking client if API proves reliable
   - Or keep for fallback/testing
