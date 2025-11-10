"""SoundWatch web application module."""

from flask import Flask, jsonify, render_template

app = Flask(__name__)

# MongoDB client and collection will be initialized when environment is set up


@app.get("/api/health")
def health():
    """Health check endpoint for the application."""
    # Simple health check; if Mongo is misconfigured, this still returns 200.
    return jsonify({"status": "ok"}), 200


@app.route('/')
def home():
    """main page - renders index.html"""
    return render_template('index.html')