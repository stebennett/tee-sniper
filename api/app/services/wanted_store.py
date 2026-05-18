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
