"""Unit tests for the ML client functions."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from client import get_db, get_interval_seconds, fake_decibels, classify_noise, run_loop


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


class TestRunLoop(unittest.TestCase):
    """Test the main run_loop function."""

    @patch("client.time.sleep")
    @patch("client.time.time")
    @patch("client.get_db")
    @patch("client.get_interval_seconds")
    @patch("client.fake_decibels")
    @patch("client.classify_noise")
    def test_run_loop_single_iteration(
        self,
        mock_classify,
        mock_fake_decibels,
        mock_get_interval,
        mock_get_db,
        mock_time,
        mock_sleep,
    ):  # pylint: disable=too-many-arguments
        """Test run_loop executes one iteration correctly."""
        # Mock dependencies
        mock_get_interval.return_value = 5
        mock_fake_decibels.return_value = 42.5
        mock_classify.return_value = "normal"
        mock_time.return_value = 1234567890.0

        # Mock database collection
        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        mock_get_db.return_value = mock_db

        # Mock environment for location
        with patch.dict(os.environ, {"ML_CLIENT_LOCATION": "test_location"}):
            # Use a side effect to break the loop after one iteration
            mock_sleep.side_effect = KeyboardInterrupt

            # Run the loop (should break after one iteration due to KeyboardInterrupt)
            try:
                run_loop()
            except KeyboardInterrupt:
                pass  # Expected behavior

        # Verify function calls
        mock_get_interval.assert_called_once()
        mock_get_db.assert_called_once()
        mock_fake_decibels.assert_called_once()
        mock_classify.assert_called_once_with(42.5)

        # Verify database insertion
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


if __name__ == "__main__":
    # Run the tests
    unittest.main()
