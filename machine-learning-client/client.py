"""
SoundWatch ML client
"""

import os
import random

from pymongo import MongoClient


def get_db():
    """Return the MongoDB database using env configuration."""
    mongodb_url = os.getenv(
        "MONGODB_URL",
        "mongodb://localhost:27017/noise_monitor",
    )
    client = MongoClient(mongodb_url)
    return client.get_database()


def get_interval_seconds() -> int:
    """Read loop interval (seconds) from env, with a safe default."""
    try:
        return int(os.getenv("ML_CLIENT_INTERVAL_SECONDS", "5"))
    except ValueError:
        return 5


def fake_decibels() -> float:
    """Generate a fake decibel reading for testing."""
    base = random.uniform(30, 45)
    # sometimes simulate louder spikes
    if random.random() < 0.2:
        base = random.uniform(50, 80)
    return round(base, 1)


def classify_noise(decibels: float) -> str:
    """Simple rule-based noise label (will be replaced with ML later)."""
    if decibels < 35:
        return "silent"
    if decibels < 45:
        return "quiet"
    if decibels < 55:
        return "normal"
    if decibels < 70:
        return "loud"
    return "very_loud"


def run_loop():
    """Main loop will use the functions above
    to periodically insert readings into the 'readings' collection.
    """

    raise NotImplementedError("ML client loop not implemented yet.")


if __name__ == "__main__":
    run_loop()
