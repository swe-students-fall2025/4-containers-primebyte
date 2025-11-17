"""Simple tests for the SoundWatch Flask web application."""

import importlib
import json
import os
import sys
from types import SimpleNamespace
from unittest import mock, TestCase


def _get_flask_app():
    """Return the Flask app instance, ensuring repo root on sys.path."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    module = importlib.import_module("app")
    return module.app


APP = _get_flask_app()


class WebAppTests(TestCase):
    """Basic integration-ish tests for the Flask endpoints."""

    def setUp(self):
        """Configure test client and stub heavy dependencies."""
        APP.config.update(TESTING=True)
        self._patchers = []

        dummy_coll = SimpleNamespace(
            insert_one=lambda *args, **kwargs: None,
            delete_many=lambda *args, **kwargs: SimpleNamespace(deleted_count=0),
        )

        def start_patch(target, new):
            patcher = mock.patch(target, new=new)
            self._patchers.append(patcher)
            return patcher.start()

        start_patch("app.measurements", new=lambda: dummy_coll)
        start_patch("app.ensure_indexes", new=lambda: None)

        self.client = APP.test_client()

    def tearDown(self):
        """Stop all applied patches."""
        for patcher in self._patchers:
            patcher.stop()

    def test_index_redirects_to_dashboard(self):
        """Root path should redirect to the dashboard route."""
        response = self.client.get("/", follow_redirects=False)
        self.assertIn(response.status_code, (301, 302))
        self.assertIn("/dashboard", response.headers["Location"])

    def test_dashboard_renders_template(self):
        """Dashboard route should return HTML content."""
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["Content-Type"])

    def test_config_default_interval(self):
        """Config endpoint should fall back to the default interval."""
        with mock.patch.dict(os.environ, {}, clear=True):
            response = self.client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(), {"interval_seconds": 5, "interval_ms": 5000}
        )

    def test_config_custom_interval(self):
        """Config endpoint should use custom interval seconds when set."""
        with mock.patch.dict(os.environ, {"ML_CLIENT_INTERVAL_SECONDS": "7"}):
            response = self.client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(), {"interval_seconds": 7, "interval_ms": 7000}
        )

    def test_receive_audio_data_inserts_measurement(self):
        """Audio endpoint should store readings and acknowledge success."""
        inserted = {}

        class DummyCollection:
            """Minimal collection stub for verifying inserts."""

            def insert_one(self, payload):
                """Capture payloads for assertions."""
                inserted.update(payload)

            def delete_many(self, *_args, **_kwargs):  # pragma: no cover
                """Expose delete_many to satisfy purge handler expectations."""
                return SimpleNamespace(deleted_count=0)

        with mock.patch("app.measurements", return_value=DummyCollection()):
            response = self.client.post(
                "/api/audio_data",
                data=json.dumps({"decibels": 42.5}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})
        self.assertEqual(inserted["rms_db"], 42.5)
        self.assertIsNone(inserted["label"])
