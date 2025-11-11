"""SoundWatch web application module."""

import os
import time
from datetime import datetime,timedelta, timezone

from flask import Flask, render_template, jsonify, redirect, url_for
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ServerSelectionTimeoutError

app = Flask(__name__)

_client = None
_db = None

def get_db():
    """Get database connection.

    Returns:
        Database: MongoDB database instance.
    """
    global _client, _db
    if _db is not None:
        return _db
    mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017/noise_monitor")
    _client = MongoClient(
        mongodb_url,
        serverSelectionTimeoutMS=2000,
        connectTimeoutMS=2000,
        socketTimeoutMS=2000,
    )

    _client.server_info()
    _db = _client.get_default_database()
    return _db

def measurements():
    """Return the 'measurements' collection."""
    db = get_db()
    return db["measurements"]

def ensure_indexes():
    """Create helpful indexes (idempotent)."""
    coll = measurements()
    coll.create_index([("ts", DESCENDING)], background=True)
    coll.create_index([("label", ASCENDING)], background=True)

@app.before_first_request
def _init():
    try:
        ensure_indexes()
    except ServerSelectionTimeoutError:
        pass

@app.route("/")
def index():
    """main page - redirect to dashboard."""
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    """dashboard page"""
    return render_template("index.html")


@app.route("/realtime")
def realtime_monitor():
    """real time monitor page"""
    return render_template("realtime.html")


@app.route("/history")
def history():
    """history page"""
    return render_template("history.html")


@app.route("/health")
def health():
    """Health check endpoint.

    Returns:
        JSON: Health status and timestamp.
    """
    status = "healthy"
    details = {}
    try:
        db = get_db()
        
        cnt = db["measurements"].estimated_document_count()
        details = {"db_ok": True, "count": int(cnt)}
    except Exception as e:  
        status = "degraded"
        details = {"db_ok": False, "error": str(e)}
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "noise-monitor-web",
        }
    )


@app.route("/api/current")
def current_noise():
    """Get current noise level API - mock data.

    Returns:
        JSON: Current noise data.
    """
    try:
        doc = measurements().find_one(sort=[("ts", DESCENDING)])
        if not doc:
            return jsonify({"message": "no data yet"}), 404

        return jsonify(
            {
                "noise_level": doc.get("label", "unknown"),
                "decibels": float(doc.get("rms_db", 0.0)),
                "timestamp": datetime.fromtimestamp(doc["ts"], tz=timezone.utc).isoformat(),
            }
        )
    except Exception as e:  # pylint: disable=broad-except
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats")
def noise_stats():
    """Get noise statistics API - mock data.

    Returns:
        JSON: Noise statistics.
    """
    try:
        minutes = int(request.args.get("minutes", 60))
    except ValueError:
        minutes = 60

    since = time.time() - minutes * 60

    pipe = [
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

    try:
        agg = list(measurements().aggregate(pipe))
        base = agg[0] if agg else {}
        base = {
            "average_db": float(base.get("avg_db", 0.0)) if base else 0.0,
            "max_db": float(base.get("max_db", 0.0)) if base else 0.0,
            "min_db": float(base.get("min_db", 0.0)) if base else 0.0,
            "data_count": int(base.get("count", 0)) if base else 0,
        }

        
        pipe_levels = [
            {"$match": {"ts": {"$gte": since}}},
            {"$group": {"_id": "$label", "n": {"$sum": 1}}},
        ]
        level_counts = {d["_id"] or "unknown": d["n"] for d in measurements().aggregate(pipe_levels)}

        return jsonify({**base, "levels": level_counts})
    except Exception as e:  # pylint: disable=broad-except
        return jsonify({"error": str(e)}), 500


@app.route("/api/history")
def noise_history():
    """Get historical noise data API - mock data.

    Returns:
        JSON: Historical noise data.
    """
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
        cur = measurements().find(q).sort("ts", DESCENDING).limit(limit)
        docs = list(cur)
        docs.reverse()  

        return jsonify(
            {
                "timestamps": [datetime.fromtimestamp(d["ts"], tz=timezone.utc).isoformat() for d in docs],
                "decibels": [float(d.get("rms_db", 0.0)) for d in docs],
                "noise_levels": [d.get("label", "unknown") for d in docs],
            }
        )
    except Exception as e:  # pylint: disable=broad-except
        return jsonify({"error": str(e)}), 500
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
