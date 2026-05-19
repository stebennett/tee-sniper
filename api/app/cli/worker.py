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
