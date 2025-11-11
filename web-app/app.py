"""SoundWatch web application module."""

import os
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, redirect, render_template, request, url_for
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

app = Flask(__name__)


# ---- DB helpers -------------------------------------------------------------
def _get_client() -> MongoClient:
    """
    Cached Mongo client. Cache lives in app.config["_MONGO_CLIENT"].
    MONGODB_URL must include a default DB name (e.g. .../noise_monitor).
    """
    client = app.config.get("_MONGO_CLIENT")
    if client is None:
        mongodb_url = os.getenv(
            "MONGODB_URL", "mongodb://localhost:27017/noise_monitor"
        )
        client = MongoClient(
            mongodb_url,
            serverSelectionTimeoutMS=2000,
            connectTimeoutMS=2000,
            socketTimeoutMS=2000,
        )
        # Fail fast if unreachable
        client.server_info()
        app.config["_MONGO_CLIENT"] = client
    return client


def get_db():
    return _get_client().get_default_database()


def measurements():
    return get_db()["measurements"]


def ensure_indexes():
    """Create helpful indexes; safe to call multiple times."""
    coll = measurements()
    coll.create_index([("ts", DESCENDING)], background=True)
    coll.create_index([("label", ASCENDING)], background=True)


# ---- Routes -----------------------------------------------------------------
@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    return render_template("index.html")


@app.route("/realtime")
def realtime_monitor():
    return render_template("realtime.html")


@app.route("/history")
def history():
    return render_template("history.html")


@app.route("/health")
def health():
    """Health check; pings DB and returns count if available."""
    try:
        ensure_indexes()  # lazy, first time we touch DB
        cnt = measurements().estimated_document_count()
        return jsonify(
            {
                "status": "healthy",
                "db_ok": True,
                "count": int(cnt),
                "service": "noise-monitor-web",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    except (ServerSelectionTimeoutError, PyMongoError) as exc:
        return (
            jsonify(
                {
                    "status": "degraded",
                    "db_ok": False,
                    "error": str(exc),
                    "service": "noise-monitor-web",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ),
            200,
        )


@app.route("/api/current")
def current_noise():
    """Return the most recent measurement."""
    try:
        doc = measurements().find_one(sort=[("ts", DESCENDING)])
        if not doc:
            return jsonify({"message": "no data yet"}), 404
        return jsonify(
            {
                "noise_level": doc.get("label", "unknown"),
                "decibels": float(doc.get("rms_db", 0.0)),
                "timestamp": datetime.fromtimestamp(
                    doc["ts"], tz=timezone.utc
                ).isoformat(),
            }
        )
    except PyMongoError as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/stats")
def noise_stats():
    """Stats over a time window (minutes=60 default)."""
    try:
        minutes = int(request.args.get("minutes", 60))
    except ValueError:
        minutes = 60
    since = time.time() - minutes * 60

    try:
        base = list(
            measurements().aggregate(
                [
                    {"$match": {"ts": {"$gte": since}}},
                    {
                        "$group": {
                            "_id": None,
                            "avg_db": {"$avg": "$rms_db"},
                            "max_db": {"$max": "$rms_db"},
                            "min_db": {"$min": "$rms_db"},
                            "count": {"$sum": 1},
                        }
                    },
                ]
            )
        )
        base = base[0] if base else {}
        level_counts = {
            d["_id"] or "unknown": d["n"]
            for d in measurements().aggregate(
                [
                    {"$match": {"ts": {"$gte": since}}},
                    {"$group": {"_id": "$label", "n": {"$sum": 1}}},
                ]
            )
        }
        return jsonify(
            {
                "average_db": float(base.get("avg_db", 0.0)) if base else 0.0,
                "max_db": float(base.get("max_db", 0.0)) if base else 0.0,
                "min_db": float(base.get("min_db", 0.0)) if base else 0.0,
                "data_count": int(base.get("count", 0)) if base else 0,
                "levels": level_counts,
            }
        )
    except PyMongoError as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/history")
def noise_history():
    """Return recent samples for charting."""
    try:
        limit = min(max(int(request.args.get("limit", 200)), 1), 1000)
    except ValueError:
        limit = 200

    minutes = request.args.get("minutes")
    q = {}
    if minutes:
        try:
            since = time.time() - int(minutes) * 60
            q = {"ts": {"$gte": since}}
        except ValueError:
            pass

    try:
        docs = list(measurements().find(q).sort("ts", DESCENDING).limit(limit))
        docs.reverse()
        return jsonify(
            {
                "timestamps": [
                    datetime.fromtimestamp(d["ts"], tz=timezone.utc).isoformat()
                    for d in docs
                ],
                "decibels": [float(d.get("rms_db", 0.0)) for d in docs],
                "noise_levels": [d.get("label", "unknown") for d in docs],
            }
        )
    except PyMongoError as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/debug/insert_one", methods=["POST", "GET"])
def debug_insert_one():
    """Insert one fake sample for quick connectivity checks."""
    try:
        doc = {"ts": time.time(), "rms_db": 55.0, "label": "normal"}
        measurements().insert_one(doc)
        return jsonify({"ok": True, "inserted": doc})
    except PyMongoError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
