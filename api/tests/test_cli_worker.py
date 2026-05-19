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
        gs.return_value.log_format = "text"
        gs.return_value.log_level = "INFO"
        main()

    run_once_mock.assert_awaited_once()
    args, kwargs = run_once_mock.call_args
    assert args[0] is fake_store
    assert kwargs["base_url"] == "https://golf.example.com"
    assert "client_factory" in kwargs
    fake_redis.aclose.assert_awaited_once()


def test_configure_logging_uses_json_formatter(monkeypatch):
    import logging as _logging

    from app.cli import worker as w

    fake_settings = MagicMock()
    fake_settings.log_format = "json"
    fake_settings.log_level = "INFO"
    with patch("app.cli.worker.get_settings", return_value=fake_settings):
        w._configure_logging()
    root = _logging.getLogger()
    assert root.handlers
    assert root.handlers[0].formatter.__class__.__name__ == "JsonFormatter"
    # restore sane logging for the rest of the suite
    _logging.getLogger().handlers = []
