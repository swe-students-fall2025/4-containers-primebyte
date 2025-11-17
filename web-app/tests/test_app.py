"""Simple tests for the SoundWatch Flask web application."""

import json
import os
import sys
from types import SimpleNamespace

import pytest


def _get_flask_app():
    """Return the Flask app instance, ensuring repo root on sys.path."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from app import app as flask_app  # pylint: disable=import-outside-toplevel

    return flask_app


app = _get_flask_app()


@pytest.fixture(name="app_client")
def client_fixture(monkeypatch):
    """Yield a Flask test client with common patches."""
    app.config.update(TESTING=True)

    # Avoid accidentally creating a real Mongo connection during tests.
    dummy_coll = SimpleNamespace(
        insert_one=lambda *args, **kwargs: None,
        delete_many=lambda *args, **kwargs: SimpleNamespace(deleted_count=0),
    )

    def _return_dummy_collection():
        return dummy_coll

    monkeypatch.setattr("app.measurements", _return_dummy_collection)

    def _noop():
        return None

    monkeypatch.setattr("app.ensure_indexes", _noop)

    with app.test_client() as test_client:
        yield test_client


def test_index_redirects_to_dashboard(app_client):
    """Root path should redirect to the dashboard route."""
    response = app_client.get("/", follow_redirects=False)
    assert response.status_code in (301, 302)
    assert "/dashboard" in response.headers["Location"]


def test_dashboard_renders_template(app_client):
    """Dashboard route should return HTML content."""
    response = app_client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]


def test_config_default_interval(app_client, monkeypatch):
    """Config endpoint should fall back to the default interval."""
    monkeypatch.delenv("ML_CLIENT_INTERVAL_SECONDS", raising=False)
    response = app_client.get("/api/config")
    assert response.status_code == 200
    assert response.get_json() == {"interval_seconds": 5, "interval_ms": 5000}


def test_config_custom_interval(app_client, monkeypatch):
    """Config endpoint should use custom interval seconds when set."""
    monkeypatch.setenv("ML_CLIENT_INTERVAL_SECONDS", "7")
    response = app_client.get("/api/config")
    assert response.status_code == 200
    assert response.get_json() == {"interval_seconds": 7, "interval_ms": 7000}


def test_receive_audio_data_inserts_measurement(app_client, monkeypatch):
    """Audio endpoint should store readings and acknowledge success."""
    inserted = {}

    class DummyCollection:
        """Minimal collection stub for verifying inserts."""

        def insert_one(self, payload):
            """Capture payloads for assertions."""
            inserted.update(payload)

        def delete_many(self, *_args, **_kwargs):  # pragma: no cover - helper only
            """Expose delete_many to satisfy purge handler expectations."""
            return SimpleNamespace(deleted_count=0)

    def _build_dummy_collection():
        return DummyCollection()

    monkeypatch.setattr("app.measurements", _build_dummy_collection)

    response = app_client.post(
        "/api/audio_data",
        data=json.dumps({"decibels": 42.5}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    assert inserted["rms_db"] == 42.5
    assert inserted["label"] is None
