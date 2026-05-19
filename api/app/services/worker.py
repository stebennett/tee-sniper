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
