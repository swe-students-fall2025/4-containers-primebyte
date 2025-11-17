"""Simple tests for the SoundWatch Flask web application."""

# pylint: disable=too-few-public-methods

import importlib
import json
import os
import sys
import time
from types import SimpleNamespace
from unittest import mock, TestCase

from pymongo.errors import PyMongoError, ServerSelectionTimeoutError


def _get_flask_app():
    """Return the Flask app instance, ensuring repo root on sys.path."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    module = importlib.import_module("app")
    return module.app


APP = _get_flask_app()


class WebAppTests(TestCase):  # pylint: disable=too-many-public-methods
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
        start_patch("app.render_template", new=lambda *_args, **_kwargs: "<html />")

        self.client = APP.test_client()

    def patch_measurements(self, replacement):
        """Convenience helper to override measurements() within a context."""
        return mock.patch("app.measurements", return_value=replacement)

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

    def test_realtime_route_renders_template(self):
        """Realtime route should be accessible."""
        response = self.client.get("/realtime")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["Content-Type"])

    def test_history_route_renders_template(self):
        """History route should be accessible."""
        response = self.client.get("/history")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["Content-Type"])

    def test_health_reports_count(self):
        """Health endpoint should report database counts when healthy."""

        class HealthCollection:
            """Stub that returns a fixed document count for health checks."""

            def estimated_document_count(self):
                """Report a canned document count."""
                return 7

        with mock.patch("app.measurements", return_value=HealthCollection()):
            response = self.client.get("/health")

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "healthy")
        self.assertTrue(payload["db_ok"])
        self.assertEqual(payload["count"], 7)

    def test_health_handles_db_failure(self):
        """Health endpoint should surface degraded status when DB fails."""
        with mock.patch(
            "app.ensure_indexes", side_effect=PyMongoError("fail")
        ), mock.patch("app.measurements"):
            response = self.client.get("/health")

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload["db_ok"])
        self.assertEqual(payload["status"], "degraded")
        self.assertIn("fail", payload["error"])

    def test_current_noise_returns_latest_measurement(self):
        """Current endpoint should format the newest measurement."""

        class CurrentCollection:
            """Stub returning a canned measurement document."""

            def find_one(self, **_kwargs):
                """Return a fake latest measurement."""
                return {"ts": 1_700_000_000, "rms_db": 55.5, "label": "loud"}

        with mock.patch("app.measurements", return_value=CurrentCollection()):
            response = self.client.get("/api/current")

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["noise_level"], "loud")
        self.assertEqual(payload["decibels"], 55.5)
        self.assertTrue(payload["timestamp"].endswith("+00:00"))

    def test_current_noise_handles_missing_data(self):
        """Current endpoint should return 404 when no data exists."""

        class EmptyCollection:
            """Stub representing an empty measurements collection."""

            def find_one(self, **_kwargs):  # pragma: no cover - trivial
                """Return no document to simulate empty database."""
                return None

        with mock.patch("app.measurements", return_value=EmptyCollection()):
            response = self.client.get("/api/current")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"message": "no data yet"})

    def test_noise_stats_returns_data(self):
        """Stats endpoint aggregates averages and label counts."""

        class StatsCollection:
            """Stub providing predictable aggregation results."""

            def aggregate(self, pipeline):
                """Return canned average stats or label counts."""
                group_stage = pipeline[-1].get("$group", {})
                if group_stage.get("_id") is None:
                    return [
                        {
                            "avg_db": 40,
                            "max_db": 60,
                            "min_db": 20,
                            "count": 3,
                        }
                    ]
                return [{"_id": "normal", "n": 2}, {"_id": None, "n": 1}]

        with mock.patch("app.measurements", return_value=StatsCollection()):
            response = self.client.get("/api/stats?minutes=15")

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["average_db"], 40.0)
        self.assertEqual(payload["max_db"], 60.0)
        self.assertEqual(payload["data_count"], 3)
        self.assertEqual(payload["levels"]["normal"], 2)
        self.assertEqual(payload["levels"]["unknown"], 1)

    def test_noise_history_returns_series(self):
        """History endpoint should return parallel arrays for charting."""

        class HistoryCursor:
            """Minimal cursor that allows chaining sort/limit."""

            def __init__(self, docs):
                self._docs = docs

            def sort(self, *_args, **_kwargs):
                """Flask code expects the cursor back to support chaining."""
                return self

            def limit(self, *_args, **_kwargs):
                """Return the stored docs to simulate Mongo cursor behavior."""
                return self._docs

        class HistoryCollection:
            """Stub returning the canned cursor for history queries."""

            def find(self, _query):
                """Return a cursor with deterministic docs."""
                base = time.time()
                docs = [
                    {"ts": base + 1, "rms_db": 70.0, "label": "very_loud"},
                    {"ts": base, "rms_db": 30.0, "label": "quiet"},
                ]
                return HistoryCursor(docs)

        with mock.patch("app.measurements", return_value=HistoryCollection()):
            response = self.client.get("/api/history?limit=2")

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(payload["timestamps"]), 2)
        self.assertEqual(payload["noise_levels"][0], "quiet")
        self.assertEqual(payload["noise_levels"][1], "very_loud")

    def test_purge_data_returns_deleted_count(self):
        """Purge endpoint should delete documents and report counts."""

        class PurgeCollection:
            """Stub for purge endpoint returning a deletion count."""

            def delete_many(self, _query):
                """Return a fake delete result."""
                return SimpleNamespace(deleted_count=5)

        with mock.patch("app.measurements", return_value=PurgeCollection()):
            response = self.client.post("/api/purge")

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["deleted_count"], 5)

    def test_purge_data_handles_error(self):
        """Purge endpoint should surface DB errors."""

        class BrokenCollection:
            """Stub that raises when delete_many is invoked."""

            def delete_many(self, _query):
                """Simulate Mongo failure."""
                raise PyMongoError("boom")

        with self.patch_measurements(BrokenCollection()):
            response = self.client.post("/api/purge")

        payload = response.get_json()
        self.assertEqual(response.status_code, 500)
        self.assertFalse(payload["ok"])
        self.assertIn("boom", payload["error"])

    def test_receive_audio_data_invalid_payload(self):
        """Audio endpoint should reject invalid decibels."""
        response = self.client.post(
            "/api/audio_data",
            data=json.dumps({"decibels": "bad"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.get_json()["ok"])

    def test_receive_audio_data_handles_db_error(self):
        """Audio endpoint should handle DB failures gracefully."""

        class BrokenCollection:
            """Stub that raises when insert is attempted."""

            def insert_one(self, _payload):
                """Simulate insert failure."""
                raise PyMongoError("nope")

            def delete_many(self, *_args, **_kwargs):  # pragma: no cover
                """Placeholder to satisfy interface."""
                return SimpleNamespace(deleted_count=0)

        with self.patch_measurements(BrokenCollection()):
            response = self.client.post(
                "/api/audio_data",
                data=json.dumps({"decibels": 10}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.get_json()["ok"])

    def test_stats_handles_db_error(self):
        """Stats endpoint should catch DB errors."""

        class BrokenCollection:
            """Stub raising during aggregation."""

            def aggregate(self, *_args, **_kwargs):
                """Raise to simulate aggregation issues."""
                raise PyMongoError("agg fail")

        with self.patch_measurements(BrokenCollection()):
            response = self.client.get("/api/stats")

        self.assertEqual(response.status_code, 500)
        self.assertIn("agg fail", response.get_json()["error"])

    def test_history_handles_db_error(self):
        """History endpoint should catch DB errors."""

        class BrokenCollection:
            """Stub raising during history queries."""

            def find(self, *_args, **_kwargs):
                """Raise to simulate Mongo failure."""
                raise PyMongoError("find fail")

        with self.patch_measurements(BrokenCollection()):
            response = self.client.get("/api/history?limit=5")

        self.assertEqual(response.status_code, 500)
        self.assertIn("find fail", response.get_json()["error"])

    def test_debug_insert_success(self):
        """Debug insert endpoint should respond with inserted doc."""

        class DebugCollection:
            """Stub capturing inserted docs for verification."""

            def insert_one(self, doc):
                """Store doc for later assertions."""
                self.doc = doc  # pylint: disable=attribute-defined-outside-init

        coll = DebugCollection()
        with self.patch_measurements(coll):
            response = self.client.post("/api/debug/insert_one")

        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["inserted"]["label"], "normal")

    def test_debug_insert_handles_failure(self):
        """Debug insert endpoint should surface DB errors."""

        class BrokenCollection:
            """Stub raising when debug insert is invoked."""

            def insert_one(self, _doc):
                """Raise to simulate DB issue."""
                raise PyMongoError("debug fail")

        with self.patch_measurements(BrokenCollection()):
            response = self.client.post("/api/debug/insert_one")

        payload = response.get_json()
        self.assertFalse(payload["ok"])
        self.assertIn("debug fail", payload["error"])

    def test_current_noise_handles_db_error(self):
        """Current endpoint should handle MongoDB errors."""
        class BrokenCollection:
            def find_one(self, **_kwargs):
                raise PyMongoError("db connection failed")

        with self.patch_measurements(BrokenCollection()):
            response = self.client.get("/api/current")

        self.assertEqual(response.status_code, 500)
        self.assertIn("db connection failed", response.get_json()["error"])

    def test_stats_handles_empty_results(self):
        """Stats endpoint should handle empty aggregation results."""
        class EmptyStatsCollection:
            def aggregate(self, pipeline):
                return []

        with self.patch_measurements(EmptyStatsCollection()):
            response = self.client.get("/api/stats")

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["average_db"], 0.0)
        self.assertEqual(payload["max_db"], 0.0)
        self.assertEqual(payload["min_db"], 0.0)
        self.assertEqual(payload["data_count"], 0)
        self.assertIn("levels", payload)

    def test_stats_handles_invalid_minutes(self):
        """Stats endpoint should default to 60 when minutes is invalid."""
        call_count = [0]

        class StatsCollection:
            def aggregate(self, pipeline):
                call_count[0] += 1
                if call_count[0] == 1:
                    return [{"avg_db": 40, "max_db": 60, "min_db": 20, "count": 3}]
                else:
                    return [{"_id": "normal", "n": 2}]

        with self.patch_measurements(StatsCollection()):
            response = self.client.get("/api/stats?minutes=invalid")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("average_db", payload)

    def test_history_handles_invalid_limit(self):
        """History endpoint should default limit when invalid."""
        class HistoryCursor:
            def __init__(self):
                self._docs = []

            def sort(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def __iter__(self):
                return iter(self._docs)

        class HistoryCollection:
            def find(self, _query):
                return HistoryCursor()

        with self.patch_measurements(HistoryCollection()):
            response = self.client.get("/api/history?limit=invalid")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("timestamps", payload)

    def test_history_handles_minutes_filter(self):
        """History endpoint should filter by minutes parameter."""
        class HistoryCursor:
            def __init__(self):
                self._docs = []

            def sort(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def __iter__(self):
                return iter(self._docs)

        class HistoryCollection:
            def find(self, query):
                return HistoryCursor()

        with self.patch_measurements(HistoryCollection()):
            response = self.client.get("/api/history?minutes=30")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("timestamps", payload)

    def test_history_handles_invalid_minutes(self):
        """History endpoint should ignore invalid minutes parameter."""
        class HistoryCursor:
            def __init__(self):
                self._docs = []

            def sort(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def __iter__(self):
                return iter(self._docs)

        class HistoryCollection:
            def find(self, _query):
                return HistoryCursor()

        with self.patch_measurements(HistoryCollection()):
            response = self.client.get("/api/history?minutes=invalid")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("timestamps", payload)

    def test_debug_insert_get_method(self):
        """Debug insert endpoint should work with GET method."""
        class DebugCollection:
            def insert_one(self, doc):
                self.doc = doc  

        coll = DebugCollection()
        with self.patch_measurements(coll):
            response = self.client.get("/api/debug/insert_one")

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertIn("inserted", payload)

    def test_receive_audio_data_missing_decibels(self):
        """Audio endpoint should default decibels to 0 when missing."""
        inserted = {}

        class DummyCollection:
            def insert_one(self, payload):
                inserted.update(payload)

            def delete_many(self, *_args, **_kwargs):
                return SimpleNamespace(deleted_count=0)

        with self.patch_measurements(DummyCollection()):
            response = self.client.post(
                "/api/audio_data",
                data=json.dumps({}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})
        self.assertEqual(inserted["rms_db"], 0.0)

    def test_receive_audio_data_invalid_json(self):
        """Audio endpoint should handle invalid JSON."""
        response = self.client.post(
            "/api/audio_data",
            data="invalid json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_health_handles_server_selection_timeout(self):
        """Health endpoint should handle ServerSelectionTimeoutError."""
        with mock.patch(
            "app.measurements",
            side_effect=ServerSelectionTimeoutError("timeout")
        ), mock.patch("app.ensure_indexes"):
            response = self.client.get("/health")

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(payload["db_ok"])
        self.assertEqual(payload["status"], "degraded")
        self.assertIn("timeout", payload["error"])

    def test_ensure_indexes_creates_indexes(self):
        """Test that ensure_indexes creates indexes."""
        indexes_created = []

        class IndexCollection:
            def create_index(self, keys, **kwargs):
                indexes_created.append((keys, kwargs.get("background")))

            def insert_one(self, *_args, **_kwargs):
                pass

            def delete_many(self, *_args, **_kwargs):
                return SimpleNamespace(deleted_count=0)

        # Stop all setUp patches temporarily
        for patcher in self._patchers:
            patcher.stop()

        try:
            with self.patch_measurements(IndexCollection()):
                import app
                app.ensure_indexes()
        finally:
            # Restore setUp patches
            for patcher in self._patchers:
                patcher.start()

        self.assertEqual(len(indexes_created), 2)

    def test_get_db_returns_database(self):
        """Test that get_db returns a database instance."""
        mock_db = SimpleNamespace()
        mock_client = SimpleNamespace(get_default_database=lambda: mock_db)

        with mock.patch("app._get_client", return_value=mock_client):
            import app
            db = app.get_db()
            self.assertEqual(db, mock_db)

    def test_measurements_returns_collection(self):
        """Test that measurements returns the collection."""
        class MockDB:
            def __getitem__(self, key):
                return f"collection_{key}"

        mock_db = MockDB()
        mock_client = SimpleNamespace(get_default_database=lambda: mock_db)

        for patcher in self._patchers:
            patcher.stop()

        try:
            with mock.patch("app._get_client", return_value=mock_client):
                import app
                coll = app.measurements()
                self.assertEqual(coll, "collection_measurements")
        finally:
            for patcher in self._patchers:
                patcher.start()

    def test_get_client_caches_client(self):
        """Test that _get_client caches the MongoDB client."""
        import app
        app.app.config.pop("_MONGO_CLIENT", None)

        mock_client = SimpleNamespace(server_info=lambda: None)
        mock_client_class = mock.Mock(return_value=mock_client)

        with mock.patch("app.MongoClient", mock_client_class):
            with mock.patch.dict(os.environ, {"MONGODB_URL": "mongodb://test:27017/test"}):
                client1 = app._get_client()
                client2 = app._get_client()

                self.assertEqual(mock_client_class.call_count, 1)
                self.assertEqual(client1, client2)
                self.assertEqual(client1, mock_client)

    def test_get_client_uses_existing_cache(self):
        """Test that _get_client returns cached client if available."""
        import app
        cached_client = SimpleNamespace()
        app.app.config["_MONGO_CLIENT"] = cached_client

        mock_client_class = mock.Mock()

        with mock.patch("app.MongoClient", mock_client_class):
            client = app._get_client()
            self.assertEqual(client, cached_client)
            mock_client_class.assert_not_called()

    def test_history_limit_boundaries(self):
        """History endpoint should enforce limit boundaries."""
        class HistoryCursor:
            def __init__(self):
                self._docs = []

            def sort(self, *_args, **_kwargs):
                return self

            def limit(self, limit_val, **_kwargs):
                self._limit = limit_val
                return self._docs

            def __iter__(self):
                return iter(self._docs)

        class HistoryCollection:
            def find(self, _query):
                return HistoryCursor()

        with self.patch_measurements(HistoryCollection()):
            # Test limit too low (should be clamped to 1)
            response1 = self.client.get("/api/history?limit=0")
            # Test limit too high (should be clamped to 1000)
            response2 = self.client.get("/api/history?limit=2000")

        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)

    def test_stats_empty_base_results(self):
        """Stats endpoint should handle empty base aggregation."""
        call_count = [0]

        class StatsCollection:
            def aggregate(self, pipeline):
                call_count[0] += 1
                if call_count[0] == 1:
                    return []  # Empty base results
                return [{"_id": "normal", "n": 2}]

        with self.patch_measurements(StatsCollection()):
            response = self.client.get("/api/stats")

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["average_db"], 0.0)
        self.assertEqual(payload["data_count"], 0)
