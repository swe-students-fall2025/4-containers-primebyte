"""SoundWatch web application module."""

import os
from datetime import datetime

from flask import Flask, render_template, jsonify, redirect, url_for
from pymongo import MongoClient

app = Flask(__name__)


def get_db():
    """Get database connection.

    Returns:
        Database: MongoDB database instance.
    """
    mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017/noise_monitor")
    client = MongoClient(mongodb_url)
    return client.get_database()


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
    return jsonify(
        {
            "noise_level": "normal",
            "decibels": 45.5,
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/stats")
def noise_stats():
    """Get noise statistics API - mock data.

    Returns:
        JSON: Noise statistics.
    """
    return jsonify(
        {
            "average_db": 42.3,
            "max_db": 67.8,
            "min_db": 25.1,
            "data_count": 150,
            "noise_level": "normal",
        }
    )


@app.route("/api/history")
def noise_history():
    """Get historical noise data API - mock data.

    Returns:
        JSON: Historical noise data.
    """
    return jsonify({"timestamps": [], "decibels": [], "noise_levels": []})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
