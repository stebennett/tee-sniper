"""Tests for the Twilio SMS notifier."""

from unittest.mock import MagicMock

from app.models.wanted import Notify
from app.services.notifications import SmsNotifier


def test_notifier_disabled_when_unconfigured_is_noop():
    notifier = SmsNotifier(account_sid=None, auth_token=None, default_from=None)
    # Must not raise and must not attempt to construct a client.
    notifier.send(Notify(to="+15550001111"), "hello")
    assert notifier.enabled is False


def test_notifier_sends_with_explicit_from():
    fake_client = MagicMock()
    notifier = SmsNotifier(
        account_sid="sid", auth_token="tok", default_from="+15559999999"
    )
    notifier._client = fake_client  # inject
    notifier.send(Notify(to="+15550001111", **{"from": "+15558888888"}), "booked!")
    fake_client.messages.create.assert_called_once_with(
        to="+15550001111", from_="+15558888888", body="booked!"
    )


def test_notifier_falls_back_to_default_from():
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


def test_notifier_warns_when_no_from_number(caplog):
    notifier = SmsNotifier(account_sid="sid", auth_token="tok", default_from=None)
    notifier._client = MagicMock()
    notifier.send(Notify(to="+15550001111"), "msg")
    assert "No 'from' number" in caplog.text
    notifier._client.messages.create.assert_not_called()
