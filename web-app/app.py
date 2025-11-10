"""SoundWatch web application module."""

from flask import Flask, render_template, jsonify
from pymongo import MongoClient
import os
from datetime import datetime, timedelta

app = Flask(__name__)


def get_db():
    """Get database connection.
    
    Returns:
        Database: MongoDB database instance.
    """
    mongodb_url = os.getenv(
        'MONGODB_URL', 
        'mongodb://localhost:27017/noise_monitor'
    )
    client = MongoClient(mongodb_url)
    return client.get_database()


@app.route('/')
def index():
    """Home page - redirects to dashboard.
    
    Returns:
        Response: Rendered index template.
    """
    return render_template('index.html')



@app.route('/health')
def health():
    """Health check endpoint.
    
    Returns:
        JSON: Health status and timestamp.
    """
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "noise-monitor-web"
    })


@app.route('/api/current')
def current_noise():
    """Get current noise level API - mock data.
    
    Returns:
        JSON: Current noise data.
    """
    return jsonify({
        'noise_level': 'normal',
        'decibels': 45.5,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/stats')
def noise_stats():
    """Get noise statistics API - mock data.
    
    Returns:
        JSON: Noise statistics.
    """
    return jsonify({
        'average_db': 42.3,
        'max_db': 67.8,
        'min_db': 25.1,
        'data_count': 150
    })


@app.route('/api/history')
def noise_history():
    """Get historical noise data API - mock data.
    
    Returns:
        JSON: Historical noise data.
    """
    return jsonify({
        'timestamps': [],
        'decibels': [],
        'noise_levels': []
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)