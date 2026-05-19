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


def _configure_logging() -> None:
    """Mirror app.main.setup_logging for the standalone worker (no app import)."""
    from pythonjsonlogger import jsonlogger

    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json":
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "time", "levelname": "level"},
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)


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
    _configure_logging()
    try:
        asyncio.run(_run())
    except Exception:  # noqa: BLE001
        logger.exception("Worker run failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
