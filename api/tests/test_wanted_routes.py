"""Endpoint tests for the /api/wanted CRUD router."""

import datetime

import pytest
from fakeredis import aioredis

from app.dependencies import get_current_session, get_wanted_store
from app.main import create_app
from app.services.wanted_store import WantedStore
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.config import get_settings

    get_settings.cache_clear()
    app = create_app()
    redis = aioredis.FakeRedis(decode_responses=True)
    store = WantedStore(redis)

    app.dependency_overrides[get_current_session] = lambda: {"base_url": "x"}
    app.dependency_overrides[get_wanted_store] = lambda: store

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _one_shot_body(**over):
    body = dict(
        target_date="2026-06-01",
        start_time="08:00",
        end_time="10:00",
        num_slots=2,
        partners=["p1"],
        credentials="enc-blob",
    )
    body.update(over)
    return body


def test_create_one_shot_returns_redacted_record(client):
    r = client.post("/api/wanted?kind=one_shot", json=_one_shot_body())
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["kind"] == "one_shot"
    assert data["has_credentials"] is True
    assert "credentials" not in data
    assert data["status"] == "pending"


def test_create_recurring_and_list(client):
    client.post("/api/wanted?kind=one_shot", json=_one_shot_body())
    client.post(
        "/api/wanted?kind=recurring",
        json={
            "day_of_week": 5,
            "start_time": "07:00",
            "end_time": "09:00",
            "num_slots": 1,
            "partners": [],
            "credentials": "blob",
        },
    )
    r = client.get("/api/wanted")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_single_and_404(client):
    created = client.post("/api/wanted?kind=one_shot", json=_one_shot_body()).json()
    assert client.get(f"/api/wanted/{created['id']}").status_code == 200
    assert client.get("/api/wanted/missing").status_code == 404


def test_patch_updates_mutable_fields(client):
    created = client.post("/api/wanted?kind=one_shot", json=_one_shot_body()).json()
    r = client.patch(
        f"/api/wanted/{created['id']}",
        json={"disabled": True, "start_time": "09:00"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "disabled"
    assert body["start_time"] == "09:00"


def test_patch_reenable_sets_pending(client):
    created = client.post("/api/wanted?kind=one_shot", json=_one_shot_body()).json()
    client.patch(f"/api/wanted/{created['id']}", json={"disabled": True})
    r = client.patch(f"/api/wanted/{created['id']}", json={"disabled": False})
    assert r.json()["status"] == "pending"


def test_delete(client):
    created = client.post("/api/wanted?kind=one_shot", json=_one_shot_body()).json()
    assert client.delete(f"/api/wanted/{created['id']}").status_code == 204
    assert client.get(f"/api/wanted/{created['id']}").status_code == 404


def test_list_filters_by_status(client):
    created = client.post("/api/wanted?kind=one_shot", json=_one_shot_body()).json()
    client.patch(f"/api/wanted/{created['id']}", json={"disabled": True})
    client.post("/api/wanted?kind=one_shot", json=_one_shot_body())
    r = client.get("/api/wanted?status=disabled")
    assert len(r.json()) == 1
