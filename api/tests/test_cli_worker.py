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
    args, kwargs = run_once_mock.call_args
    assert args[0] is fake_store
    assert kwargs["base_url"] == "https://golf.example.com"
    assert "client_factory" in kwargs
    fake_redis.aclose.assert_awaited_once()
