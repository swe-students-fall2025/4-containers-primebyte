"""Unit tests for the ML client functions."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root on path before importing client
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client import get_db, get_interval_seconds, fake_decibels, classify_noise, run_loop


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


class TestNoiseClassification(unittest.TestCase):
    """Test noise classification and generation functions."""

    def test_classify_noise_silent(self):
        """Test classification for silent noise levels."""
        self.assertEqual(classify_noise(20.0), "silent")
        self.assertEqual(classify_noise(34.9), "silent")
        self.assertEqual(classify_noise(30.0), "silent")

    def test_classify_noise_quiet(self):
        """Test classification for quiet noise levels."""
        self.assertEqual(classify_noise(35.0), "quiet")
        self.assertEqual(classify_noise(40.0), "quiet")
        self.assertEqual(classify_noise(44.9), "quiet")

    def test_classify_noise_normal(self):
        """Test classification for normal noise levels."""
        self.assertEqual(classify_noise(45.0), "normal")
        self.assertEqual(classify_noise(50.0), "normal")
        self.assertEqual(classify_noise(54.9), "normal")

    def test_classify_noise_loud(self):
        """Test classification for loud noise levels."""
        self.assertEqual(classify_noise(55.0), "loud")
        self.assertEqual(classify_noise(60.0), "loud")
        self.assertEqual(classify_noise(69.9), "loud")

    def test_classify_noise_very_loud(self):
        """Test classification for very loud noise levels."""
        self.assertEqual(classify_noise(70.0), "very_loud")
        self.assertEqual(classify_noise(80.0), "very_loud")
        self.assertEqual(classify_noise(100.0), "very_loud")

    def test_classify_noise_boundary_values(self):
        """Test classification with boundary values."""
        # Test exact boundary values
        self.assertEqual(classify_noise(35.0), "quiet")
        self.assertEqual(classify_noise(45.0), "normal")
        self.assertEqual(classify_noise(55.0), "loud")
        self.assertEqual(classify_noise(70.0), "very_loud")

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

    @patch("client.get_interval_seconds", return_value=1)
    @patch("client.time.sleep")
    @patch("client.fake_decibels", return_value=50.0)
    @patch("client.classify_noise", return_value="normal")
    @patch("client.get_db")
    def test_run_loop_inserts_measurement(
        self,
        mock_get_db,
        mock_classify_noise,
        mock_fake_decibels,
        mock_sleep,
        _mock_interval,
    ):
        """Ensure run_loop writes labeled readings and respects sleep."""
        mock_coll = MagicMock()
        mock_get_db.return_value = {"measurements": mock_coll}
        mock_sleep.side_effect = KeyboardInterrupt

        # Force default location behavior (avoid env leakage)
        with patch.dict(os.environ, {}, clear=True):
            run_loop()

        mock_get_db.assert_called_once()
        mock_fake_decibels.assert_called_once()
        mock_classify_noise.assert_called_once_with(50.0)
        mock_coll.insert_one.assert_called_once()
        inserted_doc = mock_coll.insert_one.call_args[0][0]
        self.assertEqual(inserted_doc["rms_db"], 50.0)
        self.assertEqual(inserted_doc["label"], "normal")
        self.assertEqual(inserted_doc["location"], "unknown")
        self.assertIn("ts", inserted_doc)
        self.assertIsInstance(inserted_doc["ts"], float)
