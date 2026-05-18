"""Tests for WantedStore Redis persistence."""

import datetime

import pytest
import pytest_asyncio
from fakeredis import aioredis

from app.models.wanted import WantedKind, WantedSlot, WantedStatus
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


def test_ttl_seconds_is_pinned_relative_to_today():
    from fakeredis import aioredis
    s = WantedStore(aioredis.FakeRedis(decode_responses=True))
    slot = _slot("t", target_date=datetime.date(2026, 6, 1))
    assert s._ttl_seconds(slot, today=datetime.date(2026, 5, 16)) == 46 * 24 * 3600
