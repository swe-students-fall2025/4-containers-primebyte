"""
SoundWatch ML client
"""

import os
import random
import time

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
        return int(os.getenv("ML_CLIENT_INTERVAL_SECONDS", "1"))
    except ValueError:
        return 1


def use_fake_data() -> bool:
    """Check if we should use fake data or real microphone input."""
    return os.getenv("USE_FAKE_DATA", "true").lower() in ("true", "1", "yes")


def fake_decibels() -> float:
    """Generate a fake decibel reading for testing."""
    base = random.uniform(30, 45)
    # sometimes simulate louder spikes
    if random.random() < 0.2:
        base = random.uniform(50, 80)
    return round(base, 1)


def _get_real_decibel_history(limit=500):
    """Fetch recent real microphone decibel readings from MongoDB.

    We use these as training data for k-means.
    """
    db = get_db()
    coll = db["measurements"]

    cursor = (
        coll.find(
            {
                "source": "real",
                "rms_db": {"$ne": None},
            }
        )
        .sort("ts", -1)
        .limit(limit)
    )

    values = []
    for doc in cursor:
        try:
            values.append(float(doc.get("rms_db", 0.0)))
        except (TypeError, ValueError):
            # Skip malformed values
            continue
    return values


def _kmeans_1d(values, k=5, max_iters=20):
    """Simple 1-D k-means implementation using pure Python.

    Returns a list of k cluster centroids.
    """
    if not values:
        return []

    values = list(values)
    n = len(values)
    k = min(k, n)  # never more clusters than points

    # If we have very few points, just use unique values as "centers"
    if n <= k:
        # pad if needed by repeating the last value
        centers = sorted(set(values))
        while len(centers) < k:
            centers.append(centers[-1])
        return centers

    values_sorted = sorted(values)

    # Initialize centers by picking evenly spaced points in the sorted list
    step = n / float(k)
    centers = [values_sorted[int(i * step)] for i in range(k)]

    for _ in range(max_iters):
        clusters = [[] for _ in range(k)]

        # Assign each value to the nearest center
        for v in values:
            nearest_idx = min(range(k), key=lambda i, val=v: abs(val - centers[i]))
            clusters[nearest_idx].append(v)

        new_centers = centers[:]
        for i in range(k):
            if clusters[i]:
                new_centers[i] = sum(clusters[i]) / float(len(clusters[i]))

        # Check for convergence
        if all(abs(new_centers[i] - centers[i]) < 1e-3 for i in range(k)):
            centers = new_centers
            break

        centers = new_centers

    return centers


def classify_noise_ml(decibels: float) -> str:
    """ML-based classification using k-means clustering.

    Uses recent real microphone readings from MongoDB as training data.
    If we don't have enough data yet, falls back to the hardcoded thresholds.
    """
    history = _get_real_decibel_history(limit=500)

    # Not enough data to cluster yet – use the simple thresholds
    if len(history) < 10:
        return classify_noise_hardcoded(decibels)

    centers = _kmeans_1d(history, k=5)

    if not centers:
        return classify_noise_hardcoded(decibels)

    # Sort centers from quietest to loudest
    ordered = sorted(enumerate(centers), key=lambda pair: pair[1])

    # Map cluster index -> label based on center order
    labels_in_order = ["silent", "quiet", "normal", "loud", "very_loud"]
    cluster_to_label = {}

    for label, (idx, _) in zip(labels_in_order, ordered):
        cluster_to_label[idx] = label

    # Find the nearest center for this decibel value
    nearest_idx = min(range(len(centers)), key=lambda i: abs(decibels - centers[i]))
    return cluster_to_label.get(nearest_idx, "unknown")


def classify_noise_hardcoded(decibels: float) -> str:
    """Simple rule-based noise label.

    Thresholds updated for real microphone input:
    0-24: silent (muted/background)
    24-33: quiet
    33-50: normal
    50-65: loud
    65+: very_loud
    """
    if decibels < 24:
        return "silent"
    if decibels < 33:
        return "quiet"
    if decibels < 50:
        return "normal"
    if decibels < 65:
        return "loud"
    return "very_loud"


def classify_noise(decibels: float) -> str:
    """Classify noise level based on data mode."""
    if use_fake_data():
        return classify_noise_hardcoded(decibels)
    return classify_noise_ml(decibels)


def run_loop():
    """Main loop that classifies noise data.

    In FAKE mode: Generates fake data and classifies it.
    In REAL mode: Reads unlabeled data from web app and adds classifications.
    """

    interval = max(get_interval_seconds(), 1)
    # Default location must align with unit tests expecting 'unknown'
    location = os.getenv("ML_CLIENT_LOCATION", "unknown")
    coll = get_db()["measurements"]
    fake_mode = use_fake_data()

    print(
        f"Starting ML client in {'FAKE' if fake_mode else 'REAL'} data mode...",
        flush=True,
    )

    if not fake_mode:
        print(
            "Real mode: ML client will classify unlabeled data from web app.",
            flush=True,
        )
        # In real mode, process unlabeled measurements from web app
        while True:
            try:
                # Find measurements without labels (from web app microphone)
                unlabeled = coll.find({"label": None}).limit(100)

                count = 0
                for doc in unlabeled:
                    decibels = doc.get("rms_db", 0)
                    label = classify_noise(decibels)

                    # Update document with classification
                    coll.update_one({"_id": doc["_id"]}, {"$set": {"label": label}})
                    count += 1

                if count > 0:
                    print(f"Classified {count} unlabeled measurements", flush=True)

                time.sleep(interval)  # Check for new data periodically
            except KeyboardInterrupt:
                break
        return

    # Fake mode: generate and insert fake data with labels
    while True:
        try:
            decibels = fake_decibels()
            label = classify_noise(decibels)
            coll.insert_one(
                {
                    "ts": time.time(),
                    "rms_db": decibels,
                    "label": label,
                    "location": location,
                }
            )
            time.sleep(interval)
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    run_loop()
