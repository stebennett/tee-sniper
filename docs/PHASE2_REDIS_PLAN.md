# Phase 2: Redis Integration - Session Management

Implementation plan for [Issue #23](https://github.com/stebennett/tee-sniper/issues/23)

## Overview

This phase implements Redis-based session management for storing authenticated session cookies, enabling stateless API instances while maintaining user sessions.

## Prerequisites

- [x] Phase 1: API Foundation (#22) - Complete
- [x] Docker configuration with Redis (#26) - Complete

## Implementation Tasks

### Task 1: Redis Connection Factory

**File:** `api/app/dependencies.py`

Add Redis connection factory with:
- Async Redis client using `redis.asyncio`
- Connection pooling for performance
- Graceful error handling for connection failures
- Health check capability

**Changes:**
```python
from redis.asyncio import Redis, ConnectionPool
from app.config import get_settings

_redis_pool: ConnectionPool | None = None

async def get_redis_pool() -> ConnectionPool:
    """Get or create Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=10
        )
    return _redis_pool

async def get_redis() -> Redis:
    """Get Redis client from pool."""
    pool = await get_redis_pool()
    return Redis(connection_pool=pool)

async def close_redis_pool():
    """Close Redis connection pool (for shutdown)."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None
```

**Testing:** Unit test with mock Redis, integration test with real Redis via docker-compose.

---

### Task 2: Session Manager Service

**File:** `api/app/services/session_manager.py` (new file)

Implement `SessionManager` class with:
- `store_session(cookies, base_url)` - Store session, return UUID token
- `get_session(token)` - Retrieve session, refresh TTL (sliding window)
- `delete_session(token)` - Delete session (logout)
- `session_exists(token)` - Check if session is valid

**Implementation:**
```python
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class SessionError(Exception):
    """Base exception for session operations."""
    pass


class SessionNotFoundError(SessionError):
    """Session does not exist or has expired."""
    pass


class SessionManager:
    """Manages user sessions in Redis with sliding window TTL."""

    KEY_PREFIX = "session:"
    DEFAULT_TTL = 1800  # 30 minutes

    def __init__(self, redis: Redis, ttl: int = DEFAULT_TTL):
        self.redis = redis
        self.ttl = ttl

    def _key(self, token: str) -> str:
        """Generate Redis key for session token."""
        return f"{self.KEY_PREFIX}{token}"

    async def store_session(self, cookies: dict, base_url: str) -> str:
        """
        Store session cookies and return access token.

        Args:
            cookies: Dictionary of cookies from authenticated session
            base_url: The base URL of the golf course website

        Returns:
            UUID access token for the session
        """
        token = str(uuid.uuid4())
        session_data = {
            "cookies": cookies,
            "base_url": base_url,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        await self.redis.setex(
            self._key(token),
            self.ttl,
            json.dumps(session_data)
        )

        logger.info(
            "Session created",
            extra={"token_prefix": token[:8], "base_url": base_url}
        )
        return token

    async def get_session(self, token: str) -> dict:
        """
        Retrieve session data by token.

        Implements sliding window TTL - refreshes expiry on access.

        Args:
            token: The session access token

        Returns:
            Session data dictionary

        Raises:
            SessionNotFoundError: If session doesn't exist or expired
        """
        key = self._key(token)
        data = await self.redis.get(key)

        if data is None:
            logger.warning(
                "Session not found",
                extra={"token_prefix": token[:8]}
            )
            raise SessionNotFoundError(f"Session not found or expired")

        # Refresh TTL on access (sliding window)
        await self.redis.expire(key, self.ttl)

        logger.debug(
            "Session accessed",
            extra={"token_prefix": token[:8]}
        )
        return json.loads(data)

    async def delete_session(self, token: str) -> bool:
        """
        Delete session (logout).

        Args:
            token: The session access token

        Returns:
            True if session was deleted, False if it didn't exist
        """
        result = await self.redis.delete(self._key(token))
        deleted = result > 0

        logger.info(
            "Session deleted" if deleted else "Session delete attempted (not found)",
            extra={"token_prefix": token[:8], "deleted": deleted}
        )
        return deleted

    async def session_exists(self, token: str) -> bool:
        """
        Check if session exists without refreshing TTL.

        Args:
            token: The session access token

        Returns:
            True if session exists, False otherwise
        """
        return await self.redis.exists(self._key(token)) > 0

    async def get_ttl(self, token: str) -> int:
        """
        Get remaining TTL for a session.

        Args:
            token: The session access token

        Returns:
            Remaining TTL in seconds, -2 if key doesn't exist
        """
        return await self.redis.ttl(self._key(token))
```

**Testing:**
- Unit tests with mock Redis client
- Test store/get/delete operations
- Test sliding window TTL refresh
- Test error cases (not found, expired)

---

### Task 3: Session Dependency Injection

**File:** `api/app/dependencies.py`

Add dependencies for:
- `get_session_manager()` - Provides SessionManager instance
- `get_current_session()` - Extracts Bearer token, validates, returns session data
- Returns 401 Unauthorized for invalid/missing tokens

**Implementation:**
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.session_manager import SessionManager, SessionNotFoundError

security = HTTPBearer()

async def get_session_manager(
    redis: Redis = Depends(get_redis)
) -> SessionManager:
    """Get SessionManager instance."""
    return SessionManager(redis)

async def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session_manager: SessionManager = Depends(get_session_manager)
) -> dict:
    """
    Validate Bearer token and return session data.

    Raises:
        HTTPException: 401 if token is invalid or expired
    """
    try:
        return await session_manager.get_session(credentials.credentials)
    except SessionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"}
        )
```

---

### Task 4: Update Health Check for Redis

**File:** `api/app/main.py`

Update health check endpoint to include Redis connectivity status:

```python
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with Redis status."""
    redis_healthy = False
    try:
        redis = await get_redis()
        await redis.ping()
        redis_healthy = True
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")

    return HealthResponse(
        status="healthy" if redis_healthy else "degraded",
        timestamp=datetime.now(timezone.utc).isoformat(),
        redis_connected=redis_healthy
    )
```

**Update HealthResponse model** in `api/app/models/responses.py`:
```python
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    redis_connected: bool = True
```

---

### Task 5: Application Lifecycle Management

**File:** `api/app/main.py`

Update lifespan context manager to handle Redis pool:

```python
from contextlib import asynccontextmanager
from app.dependencies import close_redis_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting up...")
    yield
    logger.info("Shutting down...")
    await close_redis_pool()
```

---

### Task 6: Unit Tests

**File:** `api/tests/test_session_manager.py` (new file)

Test cases:
1. `test_store_session_returns_uuid_token`
2. `test_store_session_saves_correct_data`
3. `test_get_session_returns_stored_data`
4. `test_get_session_refreshes_ttl`
5. `test_get_session_raises_not_found_for_invalid_token`
6. `test_get_session_raises_not_found_for_expired_session`
7. `test_delete_session_removes_session`
8. `test_delete_session_returns_false_for_nonexistent`
9. `test_session_exists_returns_true_for_valid`
10. `test_session_exists_returns_false_for_invalid`

**Implementation approach:** Use `unittest.mock.AsyncMock` to mock Redis client.

---

### Task 7: Integration Tests

**File:** `api/tests/test_session_integration.py` (new file)

Integration tests with real Redis (requires docker-compose):
1. Full session lifecycle (store -> get -> delete)
2. Session expiry behavior (using short TTL)
3. Sliding window TTL refresh verification
4. Multiple concurrent sessions

**Test configuration:** Use `pytest-docker` or check for Redis availability, skip if not running.

---

### Task 8: Dependency Tests

**File:** `api/tests/test_dependencies.py` (new file)

Test cases:
1. `test_get_current_session_returns_session_data`
2. `test_get_current_session_raises_401_for_invalid_token`
3. `test_get_current_session_raises_401_for_missing_token`

---

### Task 9: Update Exports

**File:** `api/app/services/__init__.py`

```python
from .encryption import EncryptionService, EncryptionError
from .session_manager import SessionManager, SessionError, SessionNotFoundError

__all__ = [
    "EncryptionService",
    "EncryptionError",
    "SessionManager",
    "SessionError",
    "SessionNotFoundError",
]
```

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `api/app/services/session_manager.py` | Create | SessionManager class with Redis operations |
| `api/app/services/__init__.py` | Update | Export SessionManager and exceptions |
| `api/app/dependencies.py` | Update | Add Redis factory, session manager DI, auth dependency |
| `api/app/models/responses.py` | Update | Add redis_connected to HealthResponse |
| `api/app/main.py` | Update | Enhanced health check, Redis pool lifecycle |
| `api/tests/test_session_manager.py` | Create | Unit tests for SessionManager |
| `api/tests/test_session_integration.py` | Create | Integration tests with real Redis |
| `api/tests/test_dependencies.py` | Create | Tests for dependency injection |
| `api/tests/conftest.py` | Update | Add fixtures for Redis mocking |

---

## Acceptance Criteria Checklist

- [ ] Sessions are stored in Redis with correct TTL (30 minutes)
- [ ] Access tokens (UUID) can retrieve session data
- [ ] TTL refreshes on session access (sliding window)
- [ ] Invalid tokens return 401 Unauthorized
- [ ] Expired sessions are automatically cleaned up by Redis
- [ ] Health check reports Redis connectivity status
- [ ] All unit tests pass
- [ ] Integration tests pass (with Redis running)
- [ ] Code follows existing patterns (Pydantic, dependency injection)
- [ ] Structured logging for all session operations

---

## Testing Commands

```bash
# Run all tests
cd api && python -m pytest

# Run session manager tests only
cd api && python -m pytest tests/test_session_manager.py -v

# Run integration tests (requires Redis)
docker-compose up -d redis
cd api && python -m pytest tests/test_session_integration.py -v

# Run with coverage
cd api && python -m pytest --cov=app --cov-report=term-missing
```

---

## Estimated Effort

| Task | Complexity |
|------|-----------|
| Task 1: Redis Connection Factory | Low |
| Task 2: Session Manager Service | Medium |
| Task 3: Session Dependency Injection | Low |
| Task 4: Health Check Update | Low |
| Task 5: Lifecycle Management | Low |
| Task 6: Unit Tests | Medium |
| Task 7: Integration Tests | Medium |
| Task 8: Dependency Tests | Low |
| Task 9: Update Exports | Trivial |

---

## Dependencies for Next Phase

This phase enables:
- **Phase 3**: Booking Client can use SessionManager to store/retrieve authenticated sessions
- **Phase 4**: Login endpoint can create sessions, other endpoints can validate them

---

## Notes

- Redis TTL handles automatic session cleanup - no need for manual expiry jobs
- Sliding window TTL means active users stay logged in
- Session data includes `base_url` to support multiple golf course sites in future
- Token prefix logging (first 8 chars) helps debugging without exposing full tokens
