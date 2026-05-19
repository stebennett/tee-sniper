"""Tests for the wanted-slot worker run_once orchestration."""

import datetime
from unittest.mock import AsyncMock, MagicMock

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


async def test_store_update_failure_for_one_slot_does_not_block_others(store):
    await store.create(_slot("a"))
    await store.create(_slot("b"))

    real_update = store.update
    calls = {"n": 0}

    async def flaky_update(slot):
        # Fail the persist for whichever slot is processed first.
        if calls["n"] == 0:
            calls["n"] += 1
            raise RuntimeError("redis down")
        await real_update(slot)

    store.update = flaky_update
    client = _make_client([_bookable("09:00")])
    await run_once(store, **_deps(client))

    store.update = real_update
    statuses = {s.id: s.status for s in await store.list_all()}
    # Exactly one slot persisted as BOOKED; the other was attempted but its
    # persist failed — the run did NOT abort, both were processed.
    assert list(statuses.values()).count(WantedStatus.BOOKED) == 1
    assert calls["n"] == 1
