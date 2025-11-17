"""Simple tests for the SoundWatch Flask web application."""

import json
import os
import sys
from types import SimpleNamespace

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app


@pytest.fixture()
def client(monkeypatch):
    """Yield a Flask test client with common patches."""
    app.config.update(TESTING=True)

    # Avoid accidentally creating a real Mongo connection during tests.
    dummy_coll = SimpleNamespace(
        insert_one=lambda *args, **kwargs: None,
        delete_many=lambda *args, **kwargs: SimpleNamespace(deleted_count=0),
    )
    monkeypatch.setattr("app.measurements", lambda: dummy_coll)
    monkeypatch.setattr("app.ensure_indexes", lambda: None)

    with app.test_client() as test_client:
        yield test_client


def test_index_redirects_to_dashboard(client):
    """Root path should redirect to the dashboard route."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (301, 302)
    assert "/dashboard" in response.headers["Location"]


def test_dashboard_renders_template(client):
    """Dashboard route should return HTML content."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]


def test_config_default_interval(client, monkeypatch):
    """Config endpoint should fall back to the default interval."""
    monkeypatch.delenv("ML_CLIENT_INTERVAL_SECONDS", raising=False)
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.get_json() == {"interval_seconds": 5, "interval_ms": 5000}


def test_config_custom_interval(client, monkeypatch):
    """Config endpoint should use custom interval seconds when set."""
    monkeypatch.setenv("ML_CLIENT_INTERVAL_SECONDS", "7")
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.get_json() == {"interval_seconds": 7, "interval_ms": 7000}


def test_receive_audio_data_inserts_measurement(client, monkeypatch):
    """Audio endpoint should store readings and acknowledge success."""
    inserted = {}

    class DummyCollection:
        def insert_one(self, payload):
            inserted.update(payload)

        def delete_many(self, *_args, **_kwargs):  # pragma: no cover - helper only
            return SimpleNamespace(deleted_count=0)

    monkeypatch.setattr("app.measurements", lambda: DummyCollection())

    response = client.post(
        "/api/audio_data",
        data=json.dumps({"decibels": 42.5}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    assert inserted["rms_db"] == 42.5
    assert inserted["label"] is None
