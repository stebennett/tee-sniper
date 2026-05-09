"""Tests for config loading."""

import json

import pytest

from tee_sniper_mcp.config import Config, ConfigError, load_config


def test_load_config_reads_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TSA_API_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("TSA_USERNAME", "alice")
    monkeypatch.setenv("TSA_PIN", "1234")
    monkeypatch.setenv("TSA_SHARED_SECRET", "s3cret")
    monkeypatch.delenv("TSA_TIME_BANDS", raising=False)

    cfg = load_config()

    assert cfg == Config(
        api_base_url="http://localhost:8000",
        username="alice",
        pin="1234",
        shared_secret="s3cret",
        time_bands_override=None,
    )


def test_load_config_strips_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TSA_API_BASE_URL", "http://localhost:8000/")
    monkeypatch.setenv("TSA_USERNAME", "alice")
    monkeypatch.setenv("TSA_PIN", "1234")
    monkeypatch.setenv("TSA_SHARED_SECRET", "s3cret")

    cfg = load_config()
    assert cfg.api_base_url == "http://localhost:8000"


def test_load_config_parses_time_bands_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TSA_API_BASE_URL", "http://x")
    monkeypatch.setenv("TSA_USERNAME", "u")
    monkeypatch.setenv("TSA_PIN", "p")
    monkeypatch.setenv("TSA_SHARED_SECRET", "s")
    monkeypatch.setenv("TSA_TIME_BANDS", json.dumps({"morning": ["07:00", "11:00"]}))

    cfg = load_config()
    assert cfg.time_bands_override == {"morning": ["07:00", "11:00"]}


def test_load_config_raises_when_missing_required(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("TSA_API_BASE_URL", "TSA_USERNAME", "TSA_PIN", "TSA_SHARED_SECRET"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(ConfigError, match="TSA_API_BASE_URL"):
        load_config()


def test_config_repr_does_not_leak_secrets() -> None:
    cfg = Config(
        api_base_url="http://x",
        username="alice",
        pin="1234",
        shared_secret="s3cret",
        time_bands_override=None,
    )
    r = repr(cfg)
    assert "1234" not in r
    assert "s3cret" not in r


def test_load_config_raises_on_invalid_time_bands_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TSA_API_BASE_URL", "http://x")
    monkeypatch.setenv("TSA_USERNAME", "u")
    monkeypatch.setenv("TSA_PIN", "p")
    monkeypatch.setenv("TSA_SHARED_SECRET", "s")
    monkeypatch.setenv("TSA_TIME_BANDS", "{not json")

    with pytest.raises(ConfigError, match="TSA_TIME_BANDS"):
        load_config()
