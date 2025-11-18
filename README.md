![Lint-free](https://github.com/swe-students-fall2025/4-containers-primebyte/actions/workflows/lint.yml/badge.svg)
[![ML Client Tests](https://github.com/swe-students-fall2025/4-containers-primebyte/actions/workflows/ml-client-tests.yml/badge.svg)](https://github.com/swe-students-fall2025/4-containers-primebyte/actions/workflows/ml-client-tests.yml)
[![Web App Tests](https://github.com/swe-students-fall2025/4-containers-primebyte/actions/workflows/web-app-tests.yml/badge.svg)](https://github.com/swe-students-fall2025/4-containers-primebyte/actions/workflows/web-app-tests.yml)

# SoundWatch

SoundWatch is a containerized system that samples ambient audio, stores decibel readings in MongoDB, and classifies each sample as **silent / quiet / normal / loud / very loud**.  
A Flask web app collects microphone data and shows dashboards, and a separate Python ML client uses k-means clustering on real mic history to assign labels.

---

## Architecture

The system runs as three Docker containers via `docker-compose`:

- **MongoDB**
  - Shared database for all measurements.
- **Web App (`web-app/`)**
  - Flask + `pymongo`
  - Receives raw `{decibels: float}` readings from the browser microphone
  - Stores each reading in MongoDB with `label=None`
  - Renders dashboard, realtime, and history views.
- **ML Client (`machine-learning-client/`)**
  - Python + `pymongo`
  - Polls MongoDB for unlabeled real measurements
  - Trains a simple 1-D k-means model over recent decibels and assigns labels
  - Falls back to rule-based thresholds when there isn't enough data yet.

---

## Team

- [Saud Alsheddy](https://github.com/Saud-Al5)
- [Jasmine Zhu](https://github.com/jasminezjr)
- [Esther Feng](https://github.com/yf2685-beep)
- [Pranathi Chinthalapani](https://github.com/PranathiChin)
- [William Chan](https://github.com/wc2184)

---

## How to Run (Docker)

1. **Clone** this repository.
2. **Create configuration file** from the example:

   ```bash
   cp .env.example .env
   ```

3. **Start all services:**

   ```bash
   docker-compose up --build
   ```

4. **Open the web app** at http://localhost:5000 and allow microphone access in the browser.

MongoDB will be seeded automatically as the ML client runs (fake or real mode); no manual starter data is required.

---

## Configuration (`.env`)

All services read configuration from `.env` in the repo root. Simply copying `.env.example` to `.env` provides defaults that work, no additional configuration needed unless you want to test without a microphone or use fake data generation, below are the key variables you can change.

**Key variables:**

- `MONGODB_URL` – e.g. `mongodb://mongodb:27017/noise_monitor`
- `ML_CLIENT_INTERVAL_SECONDS` – loop interval in seconds (default `1`)
- `USE_FAKE_DATA`
  - `true` – ML client generates synthetic measurements
  - `false` – web app sends real mic readings, ML client classifies them
- `FLASK_APP` – Flask entry point (default `app.py`)
- `FLASK_ENV` – Flask environment (`development`, etc.)

---

## Tests & Coverage

Each subsystem has its own tests and CI workflow:

### Machine Learning Client
```bash
cd machine-learning-client
pipenv install --dev
pipenv run pytest --cov=client --cov-report=term-missing
```

### Web App
```bash
cd web-app
pipenv install --dev
pipenv run pytest --cov=app --cov-report=term-missing
```

GitHub Actions runs both `ml-client-tests` and `web-app-tests` on each push and pull request; their status is shown in the badges at the top of this file.

---

## Quick Troubleshooting

### Containers exit immediately
- Ensure `.env` exists (`cp .env.example .env`)
- Check logs: `docker-compose logs web-app`, `ml-client`, `mongodb`

### No data on dashboard
- **Fake mode:** `USE_FAKE_DATA=true` and ML client must be running
- **Real mode:** `USE_FAKE_DATA=false`, allow microphone access, click "Start Microphone"

### Database connection errors
- Confirm `MONGODB_URL` and Docker port mappings match `docker-compose.yml`
