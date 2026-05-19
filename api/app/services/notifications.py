"""Optional Twilio SMS notifications for the wanted-slot worker."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.models.wanted import Notify

if TYPE_CHECKING:
    from twilio.rest import Client

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

    def _ensure_client(self) -> "Client":
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
