"""Tests for the partners loader service."""

import json
from pathlib import Path

import pytest

from app.services.partners import PartnersService


def test_load_returns_empty_when_path_is_none() -> None:
    service = PartnersService(None)
    assert service.load() == []


def test_load_returns_empty_when_file_missing(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    missing = tmp_path / "missing.json"
    service = PartnersService(str(missing))
    with caplog.at_level("WARNING"):
        result = service.load()
    assert result == []
    assert any("partners file" in r.message.lower() for r in caplog.records)


def test_load_returns_empty_when_file_invalid_json(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    service = PartnersService(str(bad))
    with caplog.at_level("WARNING"):
        result = service.load()
    assert result == []


def test_load_returns_partners_sorted_by_name(tmp_path: Path) -> None:
    f = tmp_path / "partners.json"
    f.write_text(json.dumps({"id2": "Bob Jones", "id1": "Alice Smith"}))
    service = PartnersService(str(f))
    result = service.load()
    assert result == [
        {"id": "id1", "name": "Alice Smith"},
        {"id": "id2", "name": "Bob Jones"},
    ]


def test_load_skips_non_string_values(tmp_path: Path) -> None:
    f = tmp_path / "partners.json"
    f.write_text(json.dumps({"id1": "Alice", "id2": 42, "id3": None}))
    service = PartnersService(str(f))
    result = service.load()
    assert result == [{"id": "id1", "name": "Alice"}]
