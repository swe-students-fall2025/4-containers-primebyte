"""Unit tests for the ML client functions."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from client import (
    get_db,
    get_interval_seconds,
    fake_decibels,
    classify_noise,
    classify_noise_ml,
    use_fake_data,
    run_loop,
)


# Add the parent directory to Python path to import client
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDatabaseFunctions(unittest.TestCase):
    """Test database-related functions."""

    @patch("client.MongoClient")
    def test_get_db_default_url(self, mock_mongo_client):
        """Test get_db function with default MongoDB URL."""
        # Mock the environment to ensure no MONGODB_URL is set
        with patch.dict(os.environ, {}, clear=True):
            # Mock the MongoClient and its methods
            mock_client_instance = MagicMock()
            mock_db = MagicMock()
            mock_mongo_client.return_value = mock_client_instance
            mock_client_instance.get_database.return_value = mock_db

            # Call the function
            result = get_db()

            # Assertions
            mock_mongo_client.assert_called_once_with(
                "mongodb://localhost:27017/noise_monitor"
            )
            mock_client_instance.get_database.assert_called_once()
            self.assertEqual(result, mock_db)

    @patch("client.MongoClient")
    def test_get_db_custom_url(self, mock_mongo_client):
        """Test get_db function with custom MongoDB URL from environment."""
        custom_url = "mongodb://custom:27017/mydb"

        with patch.dict(os.environ, {"MONGODB_URL": custom_url}):
            mock_client_instance = MagicMock()
            mock_db = MagicMock()
            mock_mongo_client.return_value = mock_client_instance
            mock_client_instance.get_database.return_value = mock_db

            result = get_db()

            mock_mongo_client.assert_called_once_with(custom_url)
            mock_client_instance.get_database.assert_called_once()
            self.assertEqual(result, mock_db)


class TestIntervalFunctions(unittest.TestCase):
    """Test interval-related functions."""

    def test_get_interval_seconds_default(self):
        """Test get_interval_seconds with default value."""
        with patch.dict(os.environ, {}, clear=True):
            interval = get_interval_seconds()
            self.assertEqual(interval, 5)

    def test_get_interval_seconds_custom(self):
        """Test get_interval_seconds with custom environment value."""
        with patch.dict(os.environ, {"ML_CLIENT_INTERVAL_SECONDS": "10"}):
            interval = get_interval_seconds()
            self.assertEqual(interval, 10)

    def test_get_interval_seconds_invalid(self):
        """Test get_interval_seconds with invalid environment value."""
        with patch.dict(os.environ, {"ML_CLIENT_INTERVAL_SECONDS": "invalid"}):
            interval = get_interval_seconds()
            self.assertEqual(interval, 5)  # Should fall back to default

    def test_get_interval_seconds_minimum(self):
        """Test get_interval_seconds ensures minimum value of 1."""
        with patch.dict(os.environ, {"ML_CLIENT_INTERVAL_SECONDS": "0"}):
            interval = get_interval_seconds()
            self.assertEqual(interval, 0)
        # The minimum enforcement happens in run_loop, not here


class TestNoiseClassification(unittest.TestCase):
    """Test noise classification and generation functions."""

    def test_classify_noise_silent(self):
        """Test classification for silent noise levels."""
        self.assertEqual(classify_noise(0.0), "silent")
        self.assertEqual(classify_noise(5.0), "silent")
        self.assertEqual(classify_noise(23.9), "silent")

    def test_classify_noise_quiet(self):
        """Test classification for quiet noise levels."""
        self.assertEqual(classify_noise(24.0), "quiet")
        self.assertEqual(classify_noise(28.0), "quiet")
        self.assertEqual(classify_noise(32.9), "quiet")

    def test_classify_noise_normal(self):
        """Test classification for normal noise levels."""
        self.assertEqual(classify_noise(33.0), "normal")
        self.assertEqual(classify_noise(40.0), "normal")
        self.assertEqual(classify_noise(49.9), "normal")

    def test_classify_noise_loud(self):
        """Test classification for loud noise levels."""
        self.assertEqual(classify_noise(50.0), "loud")
        self.assertEqual(classify_noise(60.0), "loud")
        self.assertEqual(classify_noise(64.9), "loud")

    def test_classify_noise_very_loud(self):
        """Test classification for very loud noise levels."""
        self.assertEqual(classify_noise(65.0), "very_loud")
        self.assertEqual(classify_noise(80.0), "very_loud")
        self.assertEqual(classify_noise(100.0), "very_loud")

    def test_classify_noise_boundary_values(self):
        """Test classification with boundary values."""
        # Test exact boundary values
        self.assertEqual(classify_noise(24.0), "quiet")
        self.assertEqual(classify_noise(33.0), "normal")
        self.assertEqual(classify_noise(50.0), "loud")
        self.assertEqual(classify_noise(65.0), "very_loud")

    def test_classify_noise_negative(self):
        """Test classification with negative decibel values."""
        self.assertEqual(classify_noise(-10.0), "silent")
        self.assertEqual(classify_noise(0.0), "silent")


class TestFakeDecibels(unittest.TestCase):
    """Test fake decibel generation function."""

    @patch("client.random.random")
    @patch("client.random.uniform")
    def test_fake_decibels_normal(self, mock_uniform, mock_random):
        """Test fake_decibels in normal mode (no spike)."""
        # Mock random.random to return a value that doesn't trigger spike (>= 0.2)
        mock_random.return_value = 0.5
        mock_uniform.return_value = 37.5

        result = fake_decibels()

        # Should call uniform once with normal range
        mock_uniform.assert_called_once_with(30, 45)
        self.assertEqual(result, 37.5)

    @patch("client.random.random")
    @patch("client.random.uniform")
    def test_fake_decibels_spike(self, mock_uniform, mock_random):
        """Test fake_decibels when spike is triggered."""
        # Mock random.random to return a value that triggers spike (< 0.2)
        mock_random.return_value = 0.1

        # Mock the first call (spike detection) and second call (spike value)
        mock_uniform.side_effect = [35.0, 65.0]  # base value, then spike value

        result = fake_decibels()

        # Should call uniform twice: once for base, once for spike
        self.assertEqual(mock_uniform.call_count, 2)
        mock_uniform.assert_any_call(30, 45)  # Base range
        mock_uniform.assert_any_call(50, 80)  # Spike range
        self.assertEqual(result, 65.0)

    def test_fake_decibels_range_consistency(self):
        """Test that fake_decibels returns values in expected ranges."""
        # Run multiple times to test both normal and spike scenarios
        for _ in range(100):
            decibels = fake_decibels()
            self.assertIsInstance(decibels, float)
            self.assertGreaterEqual(decibels, 30.0)
            # In rare cases with spikes, could be up to 80
            self.assertLessEqual(decibels, 80.0)

    def test_fake_decibels_rounding(self):
        """Test that fake_decibels returns rounded values."""
        # We'll mock the random generation to test rounding
        with patch("client.random.random") as mock_random, patch(
            "client.random.uniform"
        ) as mock_uniform:
            mock_random.return_value = 0.5  # No spike
            mock_uniform.return_value = 37.123456  # Not rounded

            result = fake_decibels()

            # Should be rounded to 1 decimal place
            self.assertEqual(result, 37.1)


class TestConfigurationFlags(unittest.TestCase):
    """Verify helpers that depend on environment configuration."""

    def test_use_fake_data_truthy_values(self):
        """Truthy env values should enable fake data."""
        for val in ("true", "TRUE", "1", "Yes"):
            with self.subTest(val=val):
                with patch.dict(os.environ, {"USE_FAKE_DATA": val}):
                    self.assertTrue(use_fake_data())

    def test_use_fake_data_false_values(self):
        """Falsey env values should disable fake data."""
        for val in ("false", "0", "no"):
            with self.subTest(val=val):
                with patch.dict(os.environ, {"USE_FAKE_DATA": val}):
                    self.assertFalse(use_fake_data())

    def test_classify_noise_ml_delegates_to_hardcoded(self):
        """Placeholder ML classifier should call hardcoded logic."""
        with patch("client.classify_noise_hardcoded", return_value="normal") as mock_fn:
            result = classify_noise_ml(42.0)
        self.assertEqual(result, "normal")
        mock_fn.assert_called_once_with(42.0)

    def test_classify_noise_calls_ml_when_real_mode(self):
        """classify_noise should call ML classifier when fake mode disabled."""
        with patch("client.use_fake_data", return_value=False), patch(
            "client.classify_noise_ml", return_value="ml-label"
        ) as mock_ml:
            result = classify_noise(55.0)
        self.assertEqual(result, "ml-label")
        mock_ml.assert_called_once_with(55.0)


class TestRunLoop(unittest.TestCase):
    """Test the main run_loop function."""

    def test_run_loop_single_iteration(self):
        """Test run_loop executes one iteration correctly."""
        with patch("client.classify_noise") as mock_classify, patch(
            "client.fake_decibels"
        ) as mock_fake_decibels, patch(
            "client.get_interval_seconds"
        ) as mock_get_interval, patch(
            "client.get_db"
        ) as mock_get_db, patch(
            "client.time.time"
        ) as mock_time, patch(
            "client.time.sleep"
        ) as mock_sleep:
            mock_get_interval.return_value = 5
            mock_fake_decibels.return_value = 42.5
            mock_classify.return_value = "normal"
            mock_time.return_value = 1234567890.0

            mock_collection = MagicMock()
            mock_db = MagicMock()
            mock_db.__getitem__.return_value = mock_collection
            mock_get_db.return_value = mock_db

            with patch.dict(os.environ, {"ML_CLIENT_LOCATION": "test_location"}):
                mock_sleep.side_effect = KeyboardInterrupt
                try:
                    run_loop()
                except KeyboardInterrupt:
                    pass

            mock_get_interval.assert_called_once()
            mock_get_db.assert_called_once()
            mock_fake_decibels.assert_called_once()
            mock_classify.assert_called_once_with(42.5)
            mock_collection.insert_one.assert_called_once_with(
                {
                    "ts": 1234567890.0,
                    "rms_db": 42.5,
                    "label": "normal",
                    "location": "test_location",
                }
            )

        # Verify sleep was called with correct interval
        mock_sleep.assert_called_once_with(5)

    @patch("client.time.sleep")
    @patch("client.get_db")
    @patch("client.get_interval_seconds")
    def test_run_loop_minimum_interval(
        self, mock_get_interval, mock_get_db, mock_sleep
    ):
        """Test run_loop enforces minimum interval of 1 second."""
        # Mock a zero interval (should be clamped to 1)
        mock_get_interval.return_value = 0

        # Mock database to avoid real DB calls
        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        mock_get_db.return_value = mock_db

        # Break after first iteration
        mock_sleep.side_effect = KeyboardInterrupt

        try:
            run_loop()
        except KeyboardInterrupt:
            pass

        # Should sleep with at least 1 second
        mock_sleep.assert_called_once_with(1)

    @patch("client.time.sleep")
    @patch("client.get_db")
    @patch("client.get_interval_seconds")
    def test_run_loop_default_location(
        self, mock_get_interval, mock_get_db, mock_sleep
    ):
        """Test run_loop uses default location when not specified."""
        mock_get_interval.return_value = 5

        # Mock database
        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        mock_get_db.return_value = mock_db

        # Break after first iteration
        mock_sleep.side_effect = KeyboardInterrupt

        # Clear location environment variable
        with patch.dict(os.environ, {}, clear=True):
            try:
                run_loop()
            except KeyboardInterrupt:
                pass

        # Should use default location "unknown"
        call_args = mock_collection.insert_one.call_args[0][0]
        self.assertEqual(call_args["location"], "unknown")

    @patch("client.time.sleep")
    @patch("client.get_db")
    @patch("client.get_interval_seconds")
    def test_run_loop_keyboard_interrupt(
        self, mock_get_interval, mock_get_db, mock_sleep
    ):
        """Test run_loop handles KeyboardInterrupt gracefully."""
        mock_get_interval.return_value = 5

        # Mock database
        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        mock_get_db.return_value = mock_db

        # Simulate KeyboardInterrupt on first sleep
        mock_sleep.side_effect = KeyboardInterrupt

        # This should not raise an exception
        run_loop()

        # Should have tried to sleep once
        mock_sleep.assert_called_once()

    def test_run_loop_real_mode_updates_unlabeled(self):
        """Real mode should update unlabeled measurements then sleep."""
        mock_collection = MagicMock()

        class FakeCursor:  # pylint: disable=too-few-public-methods
            """A minimal cursor stub that returns canned docs."""

            def __init__(self, docs):
                self._docs = docs

            def limit(self, *_args, **_kwargs):
                """Return the stored docs regardless of limit."""
                return self._docs

        mock_collection.find.return_value = FakeCursor([{"_id": "abc", "rms_db": 30.0}])
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = mock_collection

        with patch("client.get_interval_seconds", return_value=3), patch(
            "client.get_db", return_value=mock_db
        ), patch("client.time.sleep") as mock_sleep, patch(
            "client.classify_noise", return_value="quiet"
        ) as mock_classify, patch(
            "client.use_fake_data", return_value=False
        ) as mock_use_fake:
            mock_sleep.side_effect = KeyboardInterrupt
            run_loop()

        mock_use_fake.assert_called_once()
        mock_classify.assert_called_once_with(30.0)
        mock_collection.update_one.assert_called_once_with(
            {"_id": "abc"}, {"$set": {"label": "quiet"}}
        )
        mock_sleep.assert_called_once_with(3)


if __name__ == "__main__":
    # Run the tests
    unittest.main()
