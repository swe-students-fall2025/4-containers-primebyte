import os

from flask import Flask, jsonify, render_template
from pymongo import MongoClient

app = Flask(__name__)

# TODO Read Mongo settings from environment we load the env in docker-compose.yml

# TODO Create a Mongo client and collection (even if we don't use it yet)


@app.get("/api/health")
def health():
    # Simple health check; if Mongo is misconfigured, this still returns 200.
    return jsonify({"status": "ok"}), 200


@app.get("/")
def dashboard():
    # For Day 1, just render a placeholder dashboard.
    return render_template("dashboard.html")
