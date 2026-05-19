# Wanted Tee-Times Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user register persisted "wanted tee-time" requests (one-shot by date, or recurring by day-of-week) that a daily worker attempts to book, records outcomes for, and optionally SMS-notifies on.

**Architecture:** New Redis-backed `WantedStore`, a pure `is_due()` scheduling predicate, a `run_once()` worker orchestrator that logs in fresh per request via the existing `BookingClient`, a CRUD router under `/api/wanted`, and a `python -m app.cli.worker` entrypoint deployed as an opt-in Helm CronJob using the API image.

**Tech Stack:** Python 3.11, FastAPI, pydantic v2, redis.asyncio, Twilio Python SDK, pytest / pytest-asyncio, fakeredis, Helm.

**Spec:** `docs/superpowers/specs/2026-05-16-wanted-tee-times-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `api/app/models/wanted.py` (create) | Enums, `Attempt`, `Notify`, `WantedSlot` storage model, create/patch request models, `WantedResponse` (credential-redacted) |
| `api/app/services/wanted_store.py` (create) | Redis CRUD + `wanted:index` SET management + one-shot TTL |
| `api/app/services/scheduling.py` (create) | Pure `is_due(record, today)` predicate + `target_for(record, today)` |
| `api/app/services/notifications.py` (create) | Twilio SMS helper, no-op when unconfigured |
| `api/app/services/worker.py` (create) | `run_once()` orchestration: scan → decide → attempt → record → notify |
| `api/app/cli/__init__.py` (create) | empty package marker |
| `api/app/cli/worker.py` (create) | `python -m app.cli.worker` entrypoint |
| `api/app/routers/wanted.py` (create) | REST CRUD endpoints |
| `api/app/dependencies.py` (modify) | Extract framework-free factories for store/redis reuse |
| `api/app/config.py` (modify) | Add optional Twilio settings |
| `api/app/routers/__init__.py` (modify) | Export `wanted_router` |
| `api/app/main.py` (modify) | Register `wanted_router` |
| `api/requirements.txt` (modify) | Add `twilio`, `fakeredis` (test) |
| `api/tests/test_*.py` (create) | One test module per new unit |
| `charts/tee-sniper-api/templates/worker-cronjob.yaml` (create) | Opt-in worker CronJob (API image) |
| `charts/tee-sniper-api/values.yaml` (modify) | `worker:` block |
| `charts/tee-sniper-api/values.schema.json` (modify) | Schema for `worker:` block |
| `README.md`, `CLAUDE.md` (modify) | Document feature; tick roadmap box; update spec status |

Each task is committed independently. Run all commands from `api/` unless stated. Test runner: `.venv/bin/python -m pytest`.

---

## Task 1: Wanted-slot models

**Files:**
- Create: `api/app/models/wanted.py`
- Test: `api/tests/test_wanted_models.py`
- Modify: `api/app/models/__init__.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_wanted_models.py
"""Tests for wanted-slot pydantic models."""

import datetime

import pytest
from pydantic import ValidationError

from app.models.wanted import (
    Attempt,
    CreateOneShotRequest,
    CreateRecurringRequest,
    Notify,
    Outcome,
    PatchWantedRequest,
    WantedKind,
    WantedResponse,
    WantedSlot,
    WantedStatus,
)


def _one_shot(**over) -> WantedSlot:
    base = dict(
        id="11111111-1111-1111-1111-111111111111",
        kind=WantedKind.ONE_SHOT,
        target_date=datetime.date(2026, 6, 1),
        start_time="08:00",
        end_time="10:00",
        num_slots=2,
        partners=["p1"],
        credentials="encrypted-blob",
        notify=Notify(to="+15550001111", from_="+15550002222"),
        status=WantedStatus.PENDING,
        attempts=[],
        created_at=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
    )
    base.update(over)
    return WantedSlot(**base)


def test_wanted_slot_json_roundtrip_preserves_fields():
    slot = _one_shot()
    restored = WantedSlot.model_validate_json(slot.model_dump_json())
    assert restored == slot
    assert restored.notify.from_ == "+15550002222"


def test_recurring_slot_requires_day_of_week():
    slot = WantedSlot(
        id="22222222-2222-2222-2222-222222222222",
        kind=WantedKind.RECURRING,
        day_of_week=5,  # Saturday (Monday=0)
        start_time="07:00",
        end_time="09:00",
        num_slots=1,
        partners=[],
        credentials="blob",
        notify=None,
        status=WantedStatus.PENDING,
        attempts=[],
        created_at=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
    )
    assert slot.day_of_week == 5
    assert slot.target_date is None


def test_create_one_shot_request_rejects_end_before_start():
    with pytest.raises(ValidationError):
        CreateOneShotRequest(
            target_date=datetime.date(2026, 6, 1),
            start_time="10:00",
            end_time="08:00",
            num_slots=1,
            partners=[],
            credentials="blob",
        )


def test_create_recurring_request_validates_day_of_week_range():
    with pytest.raises(ValidationError):
        CreateRecurringRequest(
            day_of_week=7,
            start_time="08:00",
            end_time="10:00",
            num_slots=1,
            partners=[],
            credentials="blob",
        )


def test_wanted_response_redacts_credentials():
    slot = _one_shot()
    resp = WantedResponse.from_slot(slot)
    dumped = resp.model_dump()
    assert "credentials" not in dumped
    assert dumped["has_credentials"] is True
    assert dumped["notify"]["to"] == "+15550001111"


def test_patch_request_all_fields_optional():
    patch = PatchWantedRequest()
    assert patch.model_dump(exclude_unset=True) == {}


def test_attempt_and_outcome_enum_serialize():
    att = Attempt(
        ts=datetime.datetime(2026, 5, 24, tzinfo=datetime.timezone.utc),
        target_date=datetime.date(2026, 6, 1),
        outcome=Outcome.BOOKED,
        booking_id="bk-1",
    )
    assert att.model_dump()["outcome"] == "booked"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_wanted_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.wanted'`

- [ ] **Step 3: Write the models**

```python
# api/app/models/wanted.py
"""Pydantic models for wanted tee-time requests."""

from __future__ import annotations

import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class WantedKind(str, Enum):
    ONE_SHOT = "one_shot"
    RECURRING = "recurring"


class WantedStatus(str, Enum):
    PENDING = "pending"
    BOOKED = "booked"
    EXPIRED = "expired"
    DISABLED = "disabled"


class Outcome(str, Enum):
    BOOKED = "booked"
    NO_SLOTS = "no_slots"
    AUTH_FAILED = "auth_failed"
    UPSTREAM_ERROR = "upstream_error"
    BOOKING_FAILED = "booking_failed"


class Notify(BaseModel):
    to: str = Field(..., description="Destination phone number, E.164")
    from_: str | None = Field(
        default=None,
        alias="from",
        description="Sender number; falls back to server default when unset",
    )

    model_config = {"populate_by_name": True}


class Attempt(BaseModel):
    ts: datetime.datetime
    target_date: datetime.date
    outcome: Outcome
    booking_id: str | None = None
    error: str | None = None


_HHMM = r"^\d{2}:\d{2}$"


class WantedSlot(BaseModel):
    """Storage model persisted in Redis."""

    id: str
    kind: WantedKind
    target_date: datetime.date | None = None
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    end_date: datetime.date | None = None
    start_time: str = Field(..., pattern=_HHMM)
    end_time: str = Field(..., pattern=_HHMM)
    num_slots: int = Field(..., ge=1, le=4)
    partners: list[str] = Field(default_factory=list, max_length=3)
    credentials: str
    notify: Notify | None = None
    status: WantedStatus = WantedStatus.PENDING
    attempts: list[Attempt] = Field(default_factory=list)
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @model_validator(mode="after")
    def _check_kind_fields(self) -> "WantedSlot":
        if self.kind is WantedKind.ONE_SHOT and self.target_date is None:
            raise ValueError("one_shot requires target_date")
        if self.kind is WantedKind.RECURRING and self.day_of_week is None:
            raise ValueError("recurring requires day_of_week")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class _CreateBase(BaseModel):
    start_time: str = Field(..., pattern=_HHMM)
    end_time: str = Field(..., pattern=_HHMM)
    num_slots: int = Field(default=1, ge=1, le=4)
    partners: list[str] = Field(default_factory=list, max_length=3)
    credentials: str
    notify: Notify | None = None

    @model_validator(mode="after")
    def _window(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class CreateOneShotRequest(_CreateBase):
    target_date: datetime.date


class CreateRecurringRequest(_CreateBase):
    day_of_week: int = Field(..., ge=0, le=6)
    end_date: datetime.date | None = None


class PatchWantedRequest(BaseModel):
    start_time: str | None = Field(default=None, pattern=_HHMM)
    end_time: str | None = Field(default=None, pattern=_HHMM)
    num_slots: int | None = Field(default=None, ge=1, le=4)
    partners: list[str] | None = Field(default=None, max_length=3)
    notify: Notify | None = None
    disabled: bool | None = None
    credentials: str | None = None


class WantedResponse(BaseModel):
    id: str
    kind: WantedKind
    target_date: datetime.date | None
    day_of_week: int | None
    end_date: datetime.date | None
    start_time: str
    end_time: str
    num_slots: int
    partners: list[str]
    has_credentials: bool
    notify: Notify | None
    status: WantedStatus
    attempts: list[Attempt]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @classmethod
    def from_slot(cls, slot: WantedSlot) -> "WantedResponse":
        data = slot.model_dump()
        data.pop("credentials")
        data["has_credentials"] = bool(slot.credentials)
        return cls(**data)
```

- [ ] **Step 4: Export from the models package**

In `api/app/models/__init__.py`, add after the existing `from app.models.responses import (...)` block:

```python
from app.models.wanted import (
    Attempt,
    CreateOneShotRequest,
    CreateRecurringRequest,
    Notify,
    Outcome,
    PatchWantedRequest,
    WantedKind,
    WantedResponse,
    WantedSlot,
    WantedStatus,
)
```

And append these names to the `__all__` list:

```python
    "Attempt",
    "CreateOneShotRequest",
    "CreateRecurringRequest",
    "Notify",
    "Outcome",
    "PatchWantedRequest",
    "WantedKind",
    "WantedResponse",
    "WantedSlot",
    "WantedStatus",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_wanted_models.py -v`
Expected: PASS (7 passed)

- [ ] **Step 6: Commit**

```bash
git add api/app/models/wanted.py api/app/models/__init__.py api/tests/test_wanted_models.py
git commit -m "feat(api): add wanted-slot pydantic models"
```

---

## Task 2: WantedStore Redis service

**Files:**
- Create: `api/app/services/wanted_store.py`
- Test: `api/tests/test_wanted_store.py`
- Modify: `api/requirements.txt`

- [ ] **Step 1: Add fakeredis test dependency**

In `api/requirements.txt`, under the `# Testing` section, add a new line after `pytest-httpx>=0.30.0`:

```
fakeredis>=2.21.0
```

Then install it:

Run: `.venv/bin/python -m pip install "fakeredis>=2.21.0"`
Expected: `Successfully installed fakeredis-...`

- [ ] **Step 2: Write the failing test**

```python
# api/tests/test_wanted_store.py
"""Tests for WantedStore Redis persistence."""

import datetime

import pytest
import pytest_asyncio
from fakeredis import aioredis

from app.models.wanted import Notify, WantedKind, WantedSlot, WantedStatus
from app.services.wanted_store import WantedStore


def _slot(slot_id: str, **over) -> WantedSlot:
    base = dict(
        id=slot_id,
        kind=WantedKind.ONE_SHOT,
        target_date=datetime.date(2026, 6, 1),
        start_time="08:00",
        end_time="10:00",
        num_slots=1,
        partners=[],
        credentials="blob",
        notify=None,
        status=WantedStatus.PENDING,
        attempts=[],
        created_at=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
    )
    base.update(over)
    return WantedSlot(**base)


@pytest_asyncio.fixture
async def store() -> WantedStore:
    redis = aioredis.FakeRedis(decode_responses=True)
    yield WantedStore(redis)
    await redis.aclose()


async def test_create_then_get(store: WantedStore):
    slot = _slot("a")
    await store.create(slot)
    fetched = await store.get("a")
    assert fetched == slot


async def test_get_missing_returns_none(store: WantedStore):
    assert await store.get("nope") is None


async def test_list_all_returns_every_created_slot(store: WantedStore):
    await store.create(_slot("a"))
    await store.create(_slot("b"))
    ids = {s.id for s in await store.list_all()}
    assert ids == {"a", "b"}


async def test_delete_removes_record_and_index_entry(store: WantedStore):
    await store.create(_slot("a"))
    assert await store.delete("a") is True
    assert await store.get("a") is None
    assert await store.list_all() == []
    assert await store.delete("a") is False


async def test_update_persists_changes(store: WantedStore):
    await store.create(_slot("a"))
    slot = await store.get("a")
    slot.status = WantedStatus.BOOKED
    await store.update(slot)
    assert (await store.get("a")).status == WantedStatus.BOOKED


async def test_one_shot_gets_ttl_recurring_does_not(store: WantedStore):
    await store.create(_slot("one", kind=WantedKind.ONE_SHOT,
                             target_date=datetime.date(2026, 6, 1)))
    await store.create(_slot("rec", kind=WantedKind.RECURRING,
                             target_date=None, day_of_week=5))
    assert await store.redis.ttl("wanted:one") > 0
    assert await store.redis.ttl("wanted:rec") == -1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_wanted_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.wanted_store'`

- [ ] **Step 4: Write the store**

```python
# api/app/services/wanted_store.py
"""Redis persistence for wanted tee-time requests."""

import datetime
import logging

from redis.asyncio import Redis

from app.models.wanted import WantedKind, WantedSlot

logger = logging.getLogger(__name__)


class WantedStore:
    """CRUD for WantedSlot records, with a set index for enumeration."""

    KEY_PREFIX = "wanted:"
    INDEX_KEY = "wanted:index"
    ONE_SHOT_GRACE_DAYS = 30

    def __init__(self, redis: Redis):
        self.redis = redis

    def _key(self, slot_id: str) -> str:
        return f"{self.KEY_PREFIX}{slot_id}"

    def _ttl_seconds(self, slot: WantedSlot) -> int | None:
        if slot.kind is not WantedKind.ONE_SHOT or slot.target_date is None:
            return None
        expiry = slot.target_date + datetime.timedelta(days=self.ONE_SHOT_GRACE_DAYS)
        delta = expiry - datetime.date.today()
        return max(int(delta.total_seconds()), 60)

    async def create(self, slot: WantedSlot) -> None:
        await self._write(slot)
        await self.redis.sadd(self.INDEX_KEY, slot.id)
        logger.info("Wanted slot created", extra={"id": slot.id, "kind": slot.kind.value})

    async def update(self, slot: WantedSlot) -> None:
        await self._write(slot)

    async def _write(self, slot: WantedSlot) -> None:
        ttl = self._ttl_seconds(slot)
        payload = slot.model_dump_json()
        if ttl is not None:
            await self.redis.set(self._key(slot.id), payload, ex=ttl)
        else:
            await self.redis.set(self._key(slot.id), payload)

    async def get(self, slot_id: str) -> WantedSlot | None:
        raw = await self.redis.get(self._key(slot_id))
        if raw is None:
            return None
        return WantedSlot.model_validate_json(raw)

    async def list_all(self) -> list[WantedSlot]:
        ids = await self.redis.smembers(self.INDEX_KEY)
        result: list[WantedSlot] = []
        for slot_id in ids:
            slot = await self.get(slot_id)
            if slot is None:
                await self.redis.srem(self.INDEX_KEY, slot_id)  # prune expired
                continue
            result.append(slot)
        return result

    async def delete(self, slot_id: str) -> bool:
        removed = await self.redis.delete(self._key(slot_id))
        await self.redis.srem(self.INDEX_KEY, slot_id)
        return removed > 0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_wanted_store.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add api/app/services/wanted_store.py api/tests/test_wanted_store.py api/requirements.txt
git commit -m "feat(api): add Redis-backed WantedStore"
```

---

## Task 3: Scheduling predicate

**Files:**
- Create: `api/app/services/scheduling.py`
- Test: `api/tests/test_scheduling.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_scheduling.py
"""Tests for the is_due / target_for scheduling predicate."""

import datetime

from app.models.wanted import (
    Attempt,
    Notify,
    Outcome,
    WantedKind,
    WantedSlot,
    WantedStatus,
)
from app.services.scheduling import RELEASE_WINDOW_DAYS, is_due, target_for

TODAY = datetime.date(2026, 5, 16)  # a Saturday
RELEASE = TODAY + datetime.timedelta(days=RELEASE_WINDOW_DAYS)  # 2026-05-24, Sunday


def _slot(**over) -> WantedSlot:
    base = dict(
        id="x",
        kind=WantedKind.ONE_SHOT,
        target_date=RELEASE,
        start_time="08:00",
        end_time="10:00",
        num_slots=1,
        partners=[],
        credentials="blob",
        notify=None,
        status=WantedStatus.PENDING,
        attempts=[],
        created_at=datetime.datetime(2026, 5, 1, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(2026, 5, 1, tzinfo=datetime.timezone.utc),
    )
    base.update(over)
    return WantedSlot(**base)


def test_one_shot_in_release_window_is_due():
    assert is_due(_slot(target_date=RELEASE), TODAY) is True
    assert target_for(_slot(target_date=RELEASE), TODAY) == RELEASE


def test_one_shot_inside_8_day_window_is_due():
    near = TODAY + datetime.timedelta(days=3)
    assert is_due(_slot(target_date=near), TODAY) is True


def test_one_shot_beyond_release_window_not_due():
    far = RELEASE + datetime.timedelta(days=1)
    assert is_due(_slot(target_date=far), TODAY) is False


def test_one_shot_past_target_not_due():
    past = TODAY - datetime.timedelta(days=1)
    assert is_due(_slot(target_date=past), TODAY) is False


def test_terminal_or_disabled_never_due():
    assert is_due(_slot(status=WantedStatus.BOOKED), TODAY) is False
    assert is_due(_slot(status=WantedStatus.EXPIRED), TODAY) is False
    assert is_due(_slot(status=WantedStatus.DISABLED), TODAY) is False


def _recurring(**over) -> WantedSlot:
    return _slot(
        kind=WantedKind.RECURRING,
        target_date=None,
        day_of_week=RELEASE.weekday(),
        **over,
    )


def test_recurring_due_when_release_matches_day_of_week():
    assert is_due(_recurring(), TODAY) is True
    assert target_for(_recurring(), TODAY) == RELEASE


def test_recurring_not_due_when_day_of_week_mismatch():
    assert is_due(_recurring(day_of_week=(RELEASE.weekday() + 1) % 7), TODAY) is False


def test_recurring_not_due_when_occurrence_already_booked():
    booked = Attempt(
        ts=datetime.datetime(2026, 5, 16, tzinfo=datetime.timezone.utc),
        target_date=RELEASE,
        outcome=Outcome.BOOKED,
        booking_id="b1",
    )
    assert is_due(_recurring(attempts=[booked]), TODAY) is False


def test_recurring_due_again_for_a_different_occurrence():
    old = Attempt(
        ts=datetime.datetime(2026, 5, 9, tzinfo=datetime.timezone.utc),
        target_date=RELEASE - datetime.timedelta(days=7),
        outcome=Outcome.BOOKED,
        booking_id="b0",
    )
    assert is_due(_recurring(attempts=[old]), TODAY) is True


def test_recurring_past_end_date_not_due():
    assert is_due(_recurring(end_date=RELEASE - datetime.timedelta(days=1)), TODAY) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_scheduling.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.scheduling'`

- [ ] **Step 3: Write the predicate**

```python
# api/app/services/scheduling.py
"""Pure scheduling predicate: is a wanted slot due on a given day?"""

import datetime

from app.models.wanted import Outcome, WantedKind, WantedSlot, WantedStatus

RELEASE_WINDOW_DAYS = 8


def target_for(slot: WantedSlot, today: datetime.date) -> datetime.date | None:
    """The play date this slot would attempt to book if run today."""
    if slot.kind is WantedKind.ONE_SHOT:
        return slot.target_date
    release = today + datetime.timedelta(days=RELEASE_WINDOW_DAYS)
    if release.weekday() != slot.day_of_week:
        return None
    return release


def is_due(slot: WantedSlot, today: datetime.date) -> bool:
    """True if the worker should attempt this slot today."""
    if slot.status in (
        WantedStatus.BOOKED,
        WantedStatus.EXPIRED,
        WantedStatus.DISABLED,
    ):
        return False

    release = today + datetime.timedelta(days=RELEASE_WINDOW_DAYS)

    if slot.kind is WantedKind.ONE_SHOT:
        td = slot.target_date
        return td is not None and today <= td <= release

    # Recurring
    target = target_for(slot, today)
    if target is None:
        return False
    if slot.end_date is not None and target > slot.end_date:
        return False
    already_booked = any(
        a.outcome is Outcome.BOOKED and a.target_date == target
        for a in slot.attempts
    )
    return not already_booked
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_scheduling.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add api/app/services/scheduling.py api/tests/test_scheduling.py
git commit -m "feat(api): add pure is_due scheduling predicate"
```

---

## Task 4: Twilio notifications service

**Files:**
- Create: `api/app/services/notifications.py`
- Test: `api/tests/test_notifications.py`
- Modify: `api/requirements.txt`, `api/app/config.py`

- [ ] **Step 1: Add the Twilio dependency**

In `api/requirements.txt`, add a new section before `# Logging`:

```
# SMS notifications
twilio>=9.0.0
```

Run: `.venv/bin/python -m pip install "twilio>=9.0.0"`
Expected: `Successfully installed twilio-...`

- [ ] **Step 2: Add Twilio settings to config**

In `api/app/config.py`, add these fields to the `Settings` class immediately after the `partners_file` field:

```python
    # Twilio SMS (optional; required only when the worker sends notifications)
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
```

- [ ] **Step 3: Write the failing test**

```python
# api/tests/test_notifications.py
"""Tests for the Twilio SMS notifier."""

from unittest.mock import MagicMock

from app.models.wanted import Notify
from app.services.notifications import SmsNotifier


def test_notifier_disabled_when_unconfigured_is_noop():
    notifier = SmsNotifier(account_sid=None, auth_token=None, default_from=None)
    # Must not raise and must not attempt to construct a client.
    notifier.send(Notify(to="+15550001111"), "hello")
    assert notifier.enabled is False


def test_notifier_sends_with_explicit_from(monkeypatch):
    fake_client = MagicMock()
    notifier = SmsNotifier(
        account_sid="sid", auth_token="tok", default_from="+15559999999"
    )
    notifier._client = fake_client  # inject
    notifier.send(Notify(to="+15550001111", **{"from": "+15558888888"}), "booked!")
    fake_client.messages.create.assert_called_once_with(
        to="+15550001111", from_="+15558888888", body="booked!"
    )


def test_notifier_falls_back_to_default_from(monkeypatch):
    fake_client = MagicMock()
    notifier = SmsNotifier(
        account_sid="sid", auth_token="tok", default_from="+15559999999"
    )
    notifier._client = fake_client
    notifier.send(Notify(to="+15550001111"), "msg")
    fake_client.messages.create.assert_called_once_with(
        to="+15550001111", from_="+15559999999", body="msg"
    )


def test_notifier_swallows_send_errors(caplog):
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = RuntimeError("twilio down")
    notifier = SmsNotifier(
        account_sid="sid", auth_token="tok", default_from="+15559999999"
    )
    notifier._client = fake_client
    # Must not raise — notification failure never aborts a booking.
    notifier.send(Notify(to="+15550001111"), "msg")
    assert "Failed to send SMS" in caplog.text


def test_send_noop_when_notify_is_none():
    notifier = SmsNotifier(account_sid="sid", auth_token="tok", default_from="+1")
    notifier._client = MagicMock()
    notifier.send(None, "msg")
    notifier._client.messages.create.assert_not_called()
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_notifications.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.notifications'`

- [ ] **Step 5: Write the notifier**

```python
# api/app/services/notifications.py
"""Optional Twilio SMS notifications for the wanted-slot worker."""

import logging

from app.models.wanted import Notify

logger = logging.getLogger(__name__)


class SmsNotifier:
    """Sends SMS via Twilio. A no-op when credentials are not configured.

    Send failures are logged and swallowed: a notification problem must
    never abort or fail a booking attempt.
    """

    def __init__(
        self,
        account_sid: str | None,
        auth_token: str | None,
        default_from: str | None,
    ):
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._default_from = default_from
        self._client = None
        self.enabled = bool(account_sid and auth_token)

    def _ensure_client(self):
        if self._client is None:
            from twilio.rest import Client

            self._client = Client(self._account_sid, self._auth_token)
        return self._client

    def send(self, notify: Notify | None, body: str) -> None:
        if notify is None or not self.enabled:
            return
        sender = notify.from_ or self._default_from
        if not sender:
            logger.warning("No 'from' number available; skipping SMS")
            return
        try:
            client = self._ensure_client()
            client.messages.create(to=notify.to, from_=sender, body=body)
        except Exception as exc:  # noqa: BLE001 - never propagate
            logger.warning("Failed to send SMS", extra={"error": str(exc)})
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_notifications.py tests/test_config.py -v`
Expected: PASS (existing config tests still pass; 5 new pass)

- [ ] **Step 7: Commit**

```bash
git add api/app/services/notifications.py api/tests/test_notifications.py api/requirements.txt api/app/config.py
git commit -m "feat(api): add optional Twilio SMS notifier"
```

---

## Task 5: Worker orchestration (run_once)

**Files:**
- Create: `api/app/services/worker.py`
- Test: `api/tests/test_worker.py`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_worker.py
"""Tests for the wanted-slot worker run_once orchestration."""

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fakeredis import aioredis

from app.models.domain import TimeSlot
from app.models.wanted import (
    Notify,
    Outcome,
    WantedKind,
    WantedSlot,
    WantedStatus,
)
from app.services.booking_client import BookingError, LoginError
from app.services.scheduling import RELEASE_WINDOW_DAYS
from app.services.wanted_store import WantedStore
from app.services.worker import run_once

TODAY = datetime.date(2026, 5, 16)
RELEASE = TODAY + datetime.timedelta(days=RELEASE_WINDOW_DAYS)


def _slot(slot_id="a", **over) -> WantedSlot:
    base = dict(
        id=slot_id,
        kind=WantedKind.ONE_SHOT,
        target_date=RELEASE,
        start_time="08:00",
        end_time="12:00",
        num_slots=2,
        partners=["p1"],
        credentials="enc",
        notify=Notify(to="+15550001111"),
        status=WantedStatus.PENDING,
        attempts=[],
        created_at=datetime.datetime(2026, 5, 1, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(2026, 5, 1, tzinfo=datetime.timezone.utc),
    )
    base.update(over)
    return WantedSlot(**base)


@pytest_asyncio.fixture
async def store():
    redis = aioredis.FakeRedis(decode_responses=True)
    yield WantedStore(redis)
    await redis.aclose()


def _bookable(t):
    return TimeSlot(time=t, can_book=True, booking_form={"f": "1"})


def _make_client(slots, *, book_id="bk-9", login_exc=None,
                 book_exc=None, avail_exc=None):
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    if login_exc:
        client.login.side_effect = login_exc
    if avail_exc:
        client.get_availability.side_effect = avail_exc
    else:
        client.get_availability.return_value = slots
    if book_exc:
        client.book_time_slot.side_effect = book_exc
    else:
        client.book_time_slot.return_value = book_id
    client.add_partner.return_value = True
    return client


def _deps(client, *, decrypt=("user", "pin")):
    enc = MagicMock()
    enc.decrypt_credentials.return_value = decrypt
    notifier = MagicMock()
    return dict(
        client_factory=lambda base_url, **_: client,
        encryption=enc,
        notifier=notifier,
        base_url="https://golf.example.com",
        today=TODAY,
    )


async def test_successful_booking_marks_one_shot_booked(store):
    await store.create(_slot())
    client = _make_client([_bookable("09:00"), _bookable("10:00")])
    deps = _deps(client)
    await run_once(store, **deps)
    updated = await store.get("a")
    assert updated.status is WantedStatus.BOOKED
    assert updated.attempts[-1].outcome is Outcome.BOOKED
    assert updated.attempts[-1].booking_id == "bk-9"
    client.book_time_slot.assert_awaited_once()
    client.add_partner.assert_awaited_once()
    deps["notifier"].send.assert_called_once()


async def test_no_slots_in_window_records_no_slots_keeps_pending(store):
    await store.create(_slot())
    client = _make_client([TimeSlot(time="09:00", can_book=False, booking_form={})])
    await run_once(store, **_deps(client))
    updated = await store.get("a")
    assert updated.status is WantedStatus.PENDING
    assert updated.attempts[-1].outcome is Outcome.NO_SLOTS


async def test_login_failure_records_auth_failed(store):
    await store.create(_slot())
    client = _make_client([], login_exc=LoginError("bad creds"))
    await run_once(store, **_deps(client))
    updated = await store.get("a")
    assert updated.attempts[-1].outcome is Outcome.AUTH_FAILED
    assert updated.status is WantedStatus.PENDING


async def test_one_shot_past_target_marked_expired_no_attempt(store):
    await store.create(_slot(target_date=TODAY - datetime.timedelta(days=1)))
    client = _make_client([_bookable("09:00")])
    await run_once(store, **_deps(client))
    updated = await store.get("a")
    assert updated.status is WantedStatus.EXPIRED
    client.book_time_slot.assert_not_awaited()


async def test_partner_failure_is_tolerated(store):
    await store.create(_slot(partners=["p1", "p2"]))
    client = _make_client([_bookable("09:00")])
    client.add_partner.side_effect = [True, BookingError("partner busy")]
    await run_once(store, **_deps(client))
    updated = await store.get("a")
    assert updated.status is WantedStatus.BOOKED


async def test_one_failing_record_does_not_block_others(store):
    await store.create(_slot("a"))
    await store.create(_slot("b"))
    calls = {"n": 0}

    def factory(base_url, **_):
        calls["n"] += 1
        if calls["n"] == 1:
            return _make_client([], avail_exc=Exception("boom"))
        return _make_client([_bookable("09:00")])

    enc = MagicMock()
    enc.decrypt_credentials.return_value = ("u", "p")
    await run_once(
        store,
        client_factory=factory,
        encryption=enc,
        notifier=MagicMock(),
        base_url="https://x",
        today=TODAY,
    )
    statuses = {s.id: s.status for s in await store.list_all()}
    assert WantedStatus.BOOKED in statuses.values()


async def test_recurring_records_attempt_stays_pending(store):
    await store.create(
        _slot("r", kind=WantedKind.RECURRING, target_date=None,
              day_of_week=RELEASE.weekday())
    )
    client = _make_client([_bookable("09:00")])
    await run_once(store, **_deps(client))
    updated = await store.get("r")
    assert updated.status is WantedStatus.PENDING
    assert updated.attempts[-1].outcome is Outcome.BOOKED
    assert updated.attempts[-1].target_date == RELEASE


async def test_second_run_same_day_is_idempotent_for_recurring(store):
    await store.create(
        _slot("r", kind=WantedKind.RECURRING, target_date=None,
              day_of_week=RELEASE.weekday())
    )
    client = _make_client([_bookable("09:00")])
    await run_once(store, **_deps(client))
    client2 = _make_client([_bookable("09:00")])
    await run_once(store, **_deps(client2))
    updated = await store.get("r")
    assert len(updated.attempts) == 1
    client2.book_time_slot.assert_not_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_worker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.worker'`

- [ ] **Step 3: Write the worker**

```python
# api/app/services/worker.py
"""Daily worker: scan wanted slots, attempt due ones, record outcomes."""

import datetime
import logging
import random
from collections.abc import Callable

from app.models.wanted import (
    Attempt,
    Outcome,
    WantedKind,
    WantedSlot,
    WantedStatus,
)
from app.services.booking_client import (
    BookingClient,
    BookingClientError,
    BookingError,
    LoginError,
)
from app.services.scheduling import is_due, target_for
from app.services.wanted_store import WantedStore

logger = logging.getLogger(__name__)

MAX_ATTEMPTS_KEPT = 10

ClientFactory = Callable[..., BookingClient]


def _record(slot: WantedSlot, target: datetime.date, outcome: Outcome,
            booking_id: str | None = None, error: str | None = None) -> Attempt:
    att = Attempt(
        ts=datetime.datetime.now(datetime.timezone.utc),
        target_date=target,
        outcome=outcome,
        booking_id=booking_id,
        error=error,
    )
    slot.attempts.append(att)
    del slot.attempts[:-MAX_ATTEMPTS_KEPT]
    slot.updated_at = att.ts
    return att


async def _attempt(slot: WantedSlot, target: datetime.date, *,
                   client_factory: ClientFactory, encryption, base_url: str) -> Attempt:
    try:
        username, pin = encryption.decrypt_credentials(slot.credentials)
    except Exception as exc:  # noqa: BLE001
        return _record(slot, target, Outcome.AUTH_FAILED, error=str(exc))

    client = client_factory(base_url=base_url)
    try:
        async with client:
            try:
                await client.login(username, pin)
            except LoginError as exc:
                return _record(slot, target, Outcome.AUTH_FAILED, error=str(exc))

            client_date = target.strftime("%d-%m-%Y")
            try:
                slots = await client.get_availability(client_date)
            except BookingClientError as exc:
                return _record(slot, target, Outcome.UPSTREAM_ERROR, error=str(exc))

            candidates = [
                s for s in slots
                if s.can_book and slot.start_time <= s.time <= slot.end_time
            ]
            if not candidates:
                return _record(slot, target, Outcome.NO_SLOTS)

            chosen = random.choice(candidates)
            try:
                booking_id = await client.book_time_slot(chosen, slot.num_slots)
            except BookingError as exc:
                return _record(slot, target, Outcome.BOOKING_FAILED, error=str(exc))
            except BookingClientError as exc:
                return _record(slot, target, Outcome.UPSTREAM_ERROR, error=str(exc))

            for i, partner_id in enumerate(slot.partners):
                try:
                    await client.add_partner(booking_id, partner_id, i + 2)
                except (BookingClientError, BookingError) as exc:
                    logger.warning(
                        "Failed to add partner",
                        extra={"id": slot.id, "partner": partner_id,
                               "error": str(exc)},
                    )

            return _record(slot, target, Outcome.BOOKED, booking_id=booking_id)
    except Exception as exc:  # noqa: BLE001 - one record must not abort the run
        return _record(slot, target, Outcome.UPSTREAM_ERROR, error=str(exc))


async def run_once(
    store: WantedStore,
    *,
    client_factory: ClientFactory,
    encryption,
    notifier,
    base_url: str,
    today: datetime.date | None = None,
) -> None:
    today = today or datetime.date.today()
    slots = await store.list_all()
    logger.info("Worker run starting", extra={"count": len(slots), "today": str(today)})

    for slot in slots:
        # Expire stale one-shots without an attempt.
        if (
            slot.kind is WantedKind.ONE_SHOT
            and slot.status is WantedStatus.PENDING
            and slot.target_date is not None
            and slot.target_date < today
        ):
            slot.status = WantedStatus.EXPIRED
            slot.updated_at = datetime.datetime.now(datetime.timezone.utc)
            await store.update(slot)
            continue

        if not is_due(slot, today):
            continue

        target = target_for(slot, today)
        if target is None:
            continue

        att = await _attempt(
            slot, target,
            client_factory=client_factory,
            encryption=encryption,
            base_url=base_url,
        )

        if att.outcome is Outcome.BOOKED and slot.kind is WantedKind.ONE_SHOT:
            slot.status = WantedStatus.BOOKED

        await store.update(slot)

        if slot.notify is not None:
            if att.outcome is Outcome.BOOKED:
                body = (
                    f"Booked tee time for {target.isoformat()} "
                    f"({slot.num_slots} slot(s)). Booking {att.booking_id}."
                )
            else:
                body = (
                    f"Tee-time attempt for {target.isoformat()} "
                    f"failed: {att.outcome.value}."
                )
            notifier.send(slot.notify, body)

    logger.info("Worker run finished")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_worker.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add api/app/services/worker.py api/tests/test_worker.py
git commit -m "feat(api): add wanted-slot worker run_once orchestration"
```

---

## Task 6: Framework-free factories + CLI entrypoint

**Files:**
- Modify: `api/app/dependencies.py`
- Create: `api/app/cli/__init__.py`, `api/app/cli/worker.py`
- Test: `api/tests/test_cli_worker.py`

- [ ] **Step 1: Add reusable factories to dependencies.py**

In `api/app/dependencies.py`, add these functions after `get_partners_service` (around line 37). They construct objects without FastAPI's `Depends`, so the CLI can reuse them:

```python
def make_redis_client():
    """Construct a standalone Redis client (no pooling) for CLI use."""
    from redis.asyncio import Redis as _Redis

    settings = get_settings()
    return _Redis.from_url(settings.redis_url, decode_responses=True)


def make_wanted_store(redis):
    """Construct a WantedStore for the given Redis client."""
    from app.services.wanted_store import WantedStore

    return WantedStore(redis)


def make_sms_notifier():
    """Construct an SmsNotifier from settings."""
    from app.services.notifications import SmsNotifier

    settings = get_settings()
    return SmsNotifier(
        account_sid=settings.twilio_account_sid,
        auth_token=settings.twilio_auth_token,
        default_from=settings.twilio_from_number,
    )
```

- [ ] **Step 2: Write the failing test**

```python
# api/tests/test_cli_worker.py
"""Tests for the CLI worker entrypoint wiring."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.cli.worker import main


def test_main_wires_dependencies_and_invokes_run_once():
    fake_redis = MagicMock()
    fake_redis.aclose = AsyncMock()
    fake_store = MagicMock()

    with patch("app.cli.worker.make_redis_client", return_value=fake_redis), \
         patch("app.cli.worker.make_wanted_store", return_value=fake_store), \
         patch("app.cli.worker.make_sms_notifier", return_value=MagicMock()), \
         patch("app.cli.worker.get_encryption_service", return_value=MagicMock()), \
         patch("app.cli.worker.get_settings") as gs, \
         patch("app.cli.worker.run_once", new=AsyncMock()) as run_once_mock:
        gs.return_value.base_url = "https://golf.example.com"
        main()

    run_once_mock.assert_awaited_once()
    _, kwargs = run_once_mock.call_args
    assert kwargs["base_url"] == "https://golf.example.com"
    assert "client_factory" in kwargs
    fake_redis.aclose.assert_awaited_once()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cli_worker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.cli'`

- [ ] **Step 4: Create the CLI package and entrypoint**

```python
# api/app/cli/__init__.py
"""Command-line entrypoints for tee-sniper-api."""
```

```python
# api/app/cli/worker.py
"""`python -m app.cli.worker` — run one wanted-slot booking pass."""

import asyncio
import logging
import sys

from app.config import get_settings
from app.dependencies import (
    get_encryption_service,
    make_redis_client,
    make_sms_notifier,
    make_wanted_store,
)
from app.services.booking_client import BookingClient
from app.services.worker import run_once

logger = logging.getLogger(__name__)


async def _run() -> None:
    settings = get_settings()
    redis = make_redis_client()
    try:
        store = make_wanted_store(redis)
        await run_once(
            store,
            client_factory=lambda base_url, **_: BookingClient(base_url=base_url),
            encryption=get_encryption_service(),
            notifier=make_sms_notifier(),
            base_url=settings.base_url,
        )
    finally:
        await redis.aclose()


def main() -> None:
    logging.basicConfig(level=get_settings().log_level)
    try:
        asyncio.run(_run())
    except Exception:  # noqa: BLE001
        logger.exception("Worker run failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_cli_worker.py tests/test_dependencies.py -v`
Expected: PASS (new test passes; existing dependency tests still pass)

- [ ] **Step 6: Commit**

```bash
git add api/app/dependencies.py api/app/cli/ api/tests/test_cli_worker.py
git commit -m "feat(api): add framework-free factories and CLI worker entrypoint"
```

---

## Task 7: REST CRUD router

**Files:**
- Create: `api/app/routers/wanted.py`
- Test: `api/tests/test_wanted_routes.py`
- Modify: `api/app/routers/__init__.py`, `api/app/main.py`, `api/app/dependencies.py`

- [ ] **Step 1: Add a request-scoped WantedStore dependency**

In `api/app/dependencies.py`, add after `make_sms_notifier` (the function from Task 6):

```python
async def get_wanted_store(
    redis: "Redis" = Depends(get_redis),
) -> "WantedStore":
    """Request-scoped WantedStore for the API router."""
    from app.services.wanted_store import WantedStore

    return WantedStore(redis)
```

- [ ] **Step 2: Write the failing test**

```python
# api/tests/test_wanted_routes.py
"""Endpoint tests for the /api/wanted CRUD router."""

import datetime

import pytest
from fakeredis import aioredis

from app.dependencies import get_current_session, get_wanted_store
from app.main import create_app
from app.services.wanted_store import WantedStore
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.config import get_settings

    get_settings.cache_clear()
    app = create_app()
    redis = aioredis.FakeRedis(decode_responses=True)
    store = WantedStore(redis)

    app.dependency_overrides[get_current_session] = lambda: {"base_url": "x"}
    app.dependency_overrides[get_wanted_store] = lambda: store

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _one_shot_body(**over):
    body = dict(
        target_date="2026-06-01",
        start_time="08:00",
        end_time="10:00",
        num_slots=2,
        partners=["p1"],
        credentials="enc-blob",
    )
    body.update(over)
    return body


def test_create_one_shot_returns_redacted_record(client):
    r = client.post("/api/wanted?kind=one_shot", json=_one_shot_body())
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["kind"] == "one_shot"
    assert data["has_credentials"] is True
    assert "credentials" not in data
    assert data["status"] == "pending"


def test_create_recurring_and_list(client):
    client.post("/api/wanted?kind=one_shot", json=_one_shot_body())
    client.post(
        "/api/wanted?kind=recurring",
        json={
            "day_of_week": 5,
            "start_time": "07:00",
            "end_time": "09:00",
            "num_slots": 1,
            "partners": [],
            "credentials": "blob",
        },
    )
    r = client.get("/api/wanted")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_single_and_404(client):
    created = client.post("/api/wanted?kind=one_shot", json=_one_shot_body()).json()
    assert client.get(f"/api/wanted/{created['id']}").status_code == 200
    assert client.get("/api/wanted/missing").status_code == 404


def test_patch_updates_mutable_fields(client):
    created = client.post("/api/wanted?kind=one_shot", json=_one_shot_body()).json()
    r = client.patch(
        f"/api/wanted/{created['id']}",
        json={"disabled": True, "start_time": "09:00"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "disabled"
    assert body["start_time"] == "09:00"


def test_patch_reenable_sets_pending(client):
    created = client.post("/api/wanted?kind=one_shot", json=_one_shot_body()).json()
    client.patch(f"/api/wanted/{created['id']}", json={"disabled": True})
    r = client.patch(f"/api/wanted/{created['id']}", json={"disabled": False})
    assert r.json()["status"] == "pending"


def test_delete(client):
    created = client.post("/api/wanted?kind=one_shot", json=_one_shot_body()).json()
    assert client.delete(f"/api/wanted/{created['id']}").status_code == 204
    assert client.get(f"/api/wanted/{created['id']}").status_code == 404


def test_list_filters_by_status(client):
    created = client.post("/api/wanted?kind=one_shot", json=_one_shot_body()).json()
    client.patch(f"/api/wanted/{created['id']}", json={"disabled": True})
    client.post("/api/wanted?kind=one_shot", json=_one_shot_body())
    r = client.get("/api/wanted?status=disabled")
    assert len(r.json()) == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_wanted_routes.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_wanted_store'` or router 404s

- [ ] **Step 4: Write the router**

```python
# api/app/routers/wanted.py
"""CRUD endpoints for wanted tee-time requests."""

import datetime
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.dependencies import get_current_session, get_wanted_store
from app.models.wanted import (
    CreateOneShotRequest,
    CreateRecurringRequest,
    PatchWantedRequest,
    WantedKind,
    WantedResponse,
    WantedSlot,
    WantedStatus,
)
from app.services.wanted_store import WantedStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wanted", tags=["Wanted"])


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


@router.post("", response_model=WantedResponse,
             status_code=status.HTTP_201_CREATED)
async def create_wanted(
    kind: WantedKind = Query(...),
    body: dict = None,
    _session: dict = Depends(get_current_session),
    store: WantedStore = Depends(get_wanted_store),
) -> WantedResponse:
    if kind is WantedKind.ONE_SHOT:
        req = CreateOneShotRequest.model_validate(body or {})
        extra = dict(kind=kind, target_date=req.target_date)
    else:
        req = CreateRecurringRequest.model_validate(body or {})
        extra = dict(kind=kind, day_of_week=req.day_of_week,
                     end_date=req.end_date)

    now = _now()
    slot = WantedSlot(
        id=str(uuid.uuid4()),
        start_time=req.start_time,
        end_time=req.end_time,
        num_slots=req.num_slots,
        partners=req.partners,
        credentials=req.credentials,
        notify=req.notify,
        status=WantedStatus.PENDING,
        attempts=[],
        created_at=now,
        updated_at=now,
        **extra,
    )
    await store.create(slot)
    return WantedResponse.from_slot(slot)


@router.get("", response_model=list[WantedResponse])
async def list_wanted(
    status_filter: WantedStatus | None = Query(default=None, alias="status"),
    _session: dict = Depends(get_current_session),
    store: WantedStore = Depends(get_wanted_store),
) -> list[WantedResponse]:
    slots = await store.list_all()
    if status_filter is not None:
        slots = [s for s in slots if s.status is status_filter]
    return [WantedResponse.from_slot(s) for s in slots]


async def _require(store: WantedStore, slot_id: str) -> WantedSlot:
    slot = await store.get(slot_id)
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Wanted slot not found")
    return slot


@router.get("/{slot_id}", response_model=WantedResponse)
async def get_wanted(
    slot_id: str,
    _session: dict = Depends(get_current_session),
    store: WantedStore = Depends(get_wanted_store),
) -> WantedResponse:
    return WantedResponse.from_slot(await _require(store, slot_id))


@router.patch("/{slot_id}", response_model=WantedResponse)
async def patch_wanted(
    slot_id: str,
    patch: PatchWantedRequest,
    _session: dict = Depends(get_current_session),
    store: WantedStore = Depends(get_wanted_store),
) -> WantedResponse:
    slot = await _require(store, slot_id)
    fields = patch.model_dump(exclude_unset=True)

    disabled = fields.pop("disabled", None)
    for key, value in fields.items():
        setattr(slot, key, value)

    if disabled is True:
        slot.status = WantedStatus.DISABLED
    elif disabled is False and slot.status is WantedStatus.DISABLED:
        slot.status = WantedStatus.PENDING

    slot.updated_at = _now()
    # Re-validate window/kind invariants by reconstructing.
    slot = WantedSlot.model_validate(slot.model_dump())
    await store.update(slot)
    return WantedResponse.from_slot(slot)


@router.delete("/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wanted(
    slot_id: str,
    _session: dict = Depends(get_current_session),
    store: WantedStore = Depends(get_wanted_store),
) -> Response:
    deleted = await store.delete(slot_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Wanted slot not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 5: Register the router**

In `api/app/routers/__init__.py`, replace the contents with:

```python
"""API route handlers."""

from app.routers.booking import router as booking_router
from app.routers.wanted import router as wanted_router

__all__ = ["booking_router", "wanted_router"]
```

In `api/app/main.py`, change the import line
`from app.routers import booking_router` to:

```python
from app.routers import booking_router, wanted_router
```

and add after `app.include_router(booking_router)`:

```python
    app.include_router(wanted_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_wanted_routes.py -v`
Expected: PASS (7 passed)

- [ ] **Step 7: Full suite regression check**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all pre-existing tests still green)

- [ ] **Step 8: Commit**

```bash
git add api/app/routers/wanted.py api/app/routers/__init__.py api/app/main.py api/app/dependencies.py api/tests/test_wanted_routes.py
git commit -m "feat(api): add /api/wanted CRUD endpoints"
```

---

## Task 8: Helm worker CronJob

**Files:**
- Create: `charts/tee-sniper-api/templates/worker-cronjob.yaml`
- Modify: `charts/tee-sniper-api/values.yaml`, `charts/tee-sniper-api/values.schema.json`

> Note: the existing `cronjob.yaml` template serves the **Go CLI** (`cli.image`, `TS_*` env). The worker uses the **API image** and `TSA_*` env, so it gets its own dedicated, opt-in template — do not modify `cronjob.yaml`.

- [ ] **Step 1: Add the worker block to values.yaml**

In `charts/tee-sniper-api/values.yaml`, add after the `cronjobs: []` line:

```yaml
worker:
  enabled: false
  schedule: "30 6 * * *"
  suspend: false
  resources:
    requests:
      memory: 128Mi
      cpu: 100m
    limits:
      memory: 256Mi
      cpu: 500m
  # Twilio is only required when wanted-slots use SMS notify.
  twilio:
    enabled: false
    existingSecret: tee-sniper-api
```

- [ ] **Step 2: Create the CronJob template**

```yaml
# charts/tee-sniper-api/templates/worker-cronjob.yaml
{{- if .Values.worker.enabled }}
apiVersion: batch/v1
kind: CronJob
metadata:
  name: {{ include "tee-sniper-api.fullname" . }}-worker
  labels:
    {{- include "tee-sniper-api.labels" . | nindent 4 }}
    app.kubernetes.io/component: worker
spec:
  schedule: {{ .Values.worker.schedule | quote }}
  suspend: {{ .Values.worker.suspend | default false }}
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 1
      template:
        metadata:
          labels:
            {{- include "tee-sniper-api.selectorLabels" . | nindent 12 }}
            app.kubernetes.io/component: worker
        spec:
          restartPolicy: Never
          serviceAccountName: {{ include "tee-sniper-api.serviceAccountName" . }}
          automountServiceAccountToken: false
          containers:
            - name: worker
              image: {{ include "tee-sniper-api.apiImage" . | quote }}
              imagePullPolicy: {{ .Values.api.image.pullPolicy }}
              command: ["python", "-m", "app.cli.worker"]
              envFrom:
                - configMapRef:
                    name: {{ include "tee-sniper-api.fullname" . }}-config
              env:
                - name: TSA_SHARED_SECRET
                  valueFrom:
                    secretKeyRef:
                      name: {{ .Values.api.existingSecret }}
                      key: shared-secret
                {{- if .Values.redis.enabled }}
                - name: TSA_REDIS_HOST
                  value: {{ printf "%s-redis-master" .Release.Name | quote }}
                - name: TSA_REDIS_PORT
                  value: "6379"
                - name: TSA_REDIS_PASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: {{ .Values.redis.auth.existingSecret }}
                      key: {{ .Values.redis.auth.existingSecretPasswordKey }}
                - name: TSA_REDIS_URL
                  value: "redis://:$(TSA_REDIS_PASSWORD)@$(TSA_REDIS_HOST):$(TSA_REDIS_PORT)/0"
                {{- end }}
                {{- if .Values.worker.twilio.enabled }}
                - name: TSA_TWILIO_ACCOUNT_SID
                  valueFrom:
                    secretKeyRef:
                      name: {{ .Values.worker.twilio.existingSecret }}
                      key: twilio-account-sid
                - name: TSA_TWILIO_AUTH_TOKEN
                  valueFrom:
                    secretKeyRef:
                      name: {{ .Values.worker.twilio.existingSecret }}
                      key: twilio-auth-token
                - name: TSA_TWILIO_FROM_NUMBER
                  valueFrom:
                    secretKeyRef:
                      name: {{ .Values.worker.twilio.existingSecret }}
                      key: twilio-from-number
                {{- end }}
              resources:
                {{- toYaml .Values.worker.resources | nindent 16 }}
{{- end }}
```

- [ ] **Step 3: Add the worker block to values.schema.json**

Open `charts/tee-sniper-api/values.schema.json`. Inside the top-level
`"properties"` object, add a `"worker"` key alongside the existing `"api"` /
`"cli"` keys (match the file's existing indentation and add a comma after the
preceding property):

```json
    "worker": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean" },
        "schedule": { "type": "string" },
        "suspend": { "type": "boolean" },
        "resources": { "type": "object" },
        "twilio": {
          "type": "object",
          "properties": {
            "enabled": { "type": "boolean" },
            "existingSecret": { "type": "string" }
          }
        }
      }
    }
```

- [ ] **Step 4: Lint and template-render the chart**

Run: `helm lint charts/tee-sniper-api`
Expected: `1 chart(s) linted, 0 chart(s) failed`

Run: `helm template t charts/tee-sniper-api --set worker.enabled=true | grep -A2 "kind: CronJob"`
Expected: output includes a CronJob named `t-tee-sniper-api-worker`

Run: `helm template t charts/tee-sniper-api | grep -c "name: t-tee-sniper-api-worker" || true`
Expected: `0` (worker absent when `worker.enabled` is false — opt-in confirmed)

- [ ] **Step 5: Commit**

```bash
git add charts/tee-sniper-api/templates/worker-cronjob.yaml charts/tee-sniper-api/values.yaml charts/tee-sniper-api/values.schema.json
git commit -m "feat(chart): add opt-in worker CronJob using the API image"
```

---

## Task 9: Documentation

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `docs/superpowers/specs/2026-05-16-wanted-tee-times-design.md`

- [ ] **Step 1: Tick the roadmap box and add usage docs**

In `README.md`, in the Roadmap section, change the first item from:

```
- [ ] **Wanted tee-times** — persisted booking requests (one-shot by date, or recurring by day-of-week) processed by a daily worker. Design: `docs/superpowers/specs/2026-05-16-wanted-tee-times-design.md`.
```

to:

```
- [x] **Wanted tee-times** — persisted booking requests (one-shot by date, or recurring by day-of-week) processed by a daily worker. Design: `docs/superpowers/specs/2026-05-16-wanted-tee-times-design.md`.
```

Then add a new subsection under the `## API Service` → `### API Endpoints`
area (after the existing endpoint list) describing the new endpoints:

```markdown
#### Wanted tee-times

Register a request to auto-book a slot when it becomes available:

- `POST /api/wanted?kind=one_shot|recurring` — create a request
- `GET /api/wanted[?status=pending|booked|expired|disabled]` — list requests
- `GET /api/wanted/{id}` — fetch one (incl. attempt history)
- `PATCH /api/wanted/{id}` — update window/partners/notify or disable
- `DELETE /api/wanted/{id}` — remove

A daily worker (`python -m app.cli.worker`, deployed as the opt-in
`worker` Helm CronJob) processes due requests, books a matching slot, records
the outcome, and optionally sends a Twilio SMS.
```

- [ ] **Step 2: Document the worker in CLAUDE.md**

In `CLAUDE.md`, under the `### Testing` section's Python block, add:

```bash
# Run the wanted-slot worker once (needs TSA_* env, see config.py)
cd api && .venv/bin/python -m app.cli.worker
```

And add a short section after the "API Migration Workflow" section:

```markdown
## Wanted Tee-Times

Persisted auto-booking requests. Spec:
`docs/superpowers/specs/2026-05-16-wanted-tee-times-design.md`.
Plan: `docs/superpowers/plans/2026-05-16-wanted-tee-times.md`.

- Models: `api/app/models/wanted.py`
- Store: `api/app/services/wanted_store.py` (Redis `wanted:{id}` + `wanted:index`)
- Scheduling predicate: `api/app/services/scheduling.py` (`is_due`, 8-day window)
- Worker: `api/app/services/worker.py` (`run_once`), CLI `app/cli/worker.py`
- Router: `api/app/routers/wanted.py` (`/api/wanted`)
- Deploy: opt-in `worker` CronJob in `charts/tee-sniper-api`
```

- [ ] **Step 3: Flip the spec status**

In `docs/superpowers/specs/2026-05-16-wanted-tee-times-design.md`, change
`**Status:** Draft` to `**Status:** Implemented`.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md docs/superpowers/specs/2026-05-16-wanted-tee-times-design.md
git commit -m "docs: document wanted tee-times feature"
```

---

## Final Verification

- [ ] **Run the full test suite**

Run: `cd api && .venv/bin/python -m pytest -q`
Expected: all tests pass, including every new module.

- [ ] **Lint check**

Run: `cd api && .venv/bin/python -m ruff check app/`
Expected: no errors in new files.

- [ ] **Helm render sanity**

Run: `helm template t charts/tee-sniper-api --set worker.enabled=true >/dev/null && echo OK`
Expected: `OK`

---

## Self-Review Notes

**Spec coverage check:**
- Data model → Task 1 (all fields incl. `end_date`, `notify`, `attempts`, status enum). ✅
- Redis storage + index + one-shot TTL → Task 2. ✅
- Worker daily logic (one-shot in/out of window, past→expired, recurring DoW, idempotent re-run, end_date) → Tasks 3 & 5. ✅
- Attempt logic + all outcomes (booked/no_slots/auth_failed/upstream_error/booking_failed) + partial partner tolerance → Task 5. ✅
- Fresh login per attempt (no session reuse) → Task 5 `_attempt`. ✅
- API surface (POST union/GET/GET one/PATCH mutable+immutable/DELETE, credential redaction) → Task 7. ✅
- Always persist outcome; optional SMS on success and terminal failure → Tasks 4 & 5. ✅
- Deployment: opt-in API-image CronJob, daily schedule, Twilio opt-in → Task 8. ✅
- Testing matrix from spec → Tasks 1–7 test modules. ✅
- Docs + roadmap tick + spec status → Task 9. ✅
- Go removal explicitly out of scope → not in any task (correct per spec). ✅

**Type consistency check:** `WantedSlot`, `WantedStatus`, `Outcome`, `Notify.from_` (alias `from`), `WantedResponse.from_slot`, `WantedStore.{create,get,update,delete,list_all}`, `is_due`/`target_for`, `run_once(store, *, client_factory, encryption, notifier, base_url, today)`, `SmsNotifier.send(notify, body)` — names used consistently across Tasks 1–8.

**Placeholder scan:** none — every code/command step contains complete content.
