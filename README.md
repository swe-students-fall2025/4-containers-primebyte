![Lint-free](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/lint.yml/badge.svg)
[![ML Client Tests](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/ml-client-tests.yml/badge.svg)](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/ml-client-tests.yml)
[![Web App Tests](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/web-app-tests.yml/badge.svg)](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/web-app-tests.yml)

# Containerized App Exercise

Build a containerized app that uses machine learning. See [instructions](./instructions.md) for details.

# SoundWatch

SoundWatch continuously samples ambient audio, classifies each snippet into silent/quiet/normal/loud/very loud bands, and surfaces the history in a sleek Flask dashboard. MongoDB persists the decibel readings and labels so both the ML client and the web UI stay perfectly in sync across containers.

## Project Vision

The browser microphone captures raw audio decibel readings and stores them unlabeled in MongoDB via the Flask web app. The ML client continuously monitors the database for unlabeled measurements, classifies them (currently rule-based, with k-means clustering planned), and updates the documents with labels. This clean separation of concerns ensures the web app handles UI and data collection while the ML client serves as the analytical brain of the system.

**Architecture:**
- **Web App**: Captures microphone input then stores raw decibels in MongoDB (label=None)
- **ML Client**: Reads unlabeled data then classifies using thresholds/ML then updates labels

## Team

- [Saud Alsheddy](https://github.com/Saud-Al5)
- [Jasmine Zhu](https://github.com/jasminezjr)
- [Esther Feng](https://github.com/yf2685-beep)
- [Pranathi Chinthalapani](https://github.com/PranathiChin)
- [William Chan](https://github.com/wc2184)


## How to run

1. Copy env file:
```bash
cp .env.example .env
```

2. Start the services:
```bash
docker-compose up --build
```
3. Open in browser:

- http://localhost:5000/ (should go to the dashboard)


## Web App Routes (should be deleted later, not required, this is just to get an idea of what we're doing)

- `/` — renders the dashboard UI.
- `/health` — lightweight health probe with status metadata.
- `/api/current` — returns the latest noise reading.
- `/api/stats` — exposes aggregate decibel stats.
- `/api/history` — supplies historical timestamps, levels, and labels.
- `/api/purge` (POST) — deletes all measurement data from the database.
- `/api/audio_data` (POST) — receives raw audio data from browser microphone (stores unlabeled, ML client classifies later).
- `/api/config` (GET) — returns configuration settings including `ML_CLIENT_INTERVAL_SECONDS` for frontend synchronization.

## Architecture

### Data Flow
1. **Browser to Web App**: Microphone captures audio at interval set by `ML_CLIENT_INTERVAL_SECONDS`, sends raw dB to `/api/audio_data`
2. **Web App to MongoDB**: Stores measurements with `label: None`
3. **ML Client to MongoDB**: Polls for unlabeled data every `ML_CLIENT_INTERVAL_SECONDS`, classifies, updates labels
4. **Dashboard to MongoDB**: Displays classified data via `/api/current`, `/api/stats`, `/api/history`

### Modes
- **Fake Data Mode** (`USE_FAKE_DATA=true`): ML client generates synthetic data with labels
- **Real Data Mode** (`USE_FAKE_DATA=false`): Web app collects real microphone data, ML client classifies it

This separation ensures the web app focuses on UI/data collection while the ML client handles all analytical processing.

## Features

### Real Microphone Input

Capture real audio from your browser microphone:
- Click "Start Microphone" on the dashboard
- Browser will request microphone permissions
- Audio data is sent to the server at the interval configured in `ML_CLIENT_INTERVAL_SECONDS`
- Click "Stop Microphone" to end capture

**Noise Level Thresholds (device-calibrated) should be changed if mismatch on different users:**
- <24 dB: Silent (muted/background)
- 24–33 dB: Quiet
- 33–50 dB: Normal
- 50–65 dB: Loud
- 65+ dB: Very Loud

### Data Management

Use the "Purge All Data" button on the dashboard to clear all historical measurements from the database.

## Environment Variables
All services read configuration from a `.env` file in the project root.

To start:
```bash
cp .env.example .env
```

- `MONGODB_URL` — MongoDB connection string (default: `mongodb://localhost:27017/noise_monitor`)
- `ML_CLIENT_INTERVAL_SECONDS` — How often ML client checks for unlabeled data to classify in real mode, or generates fake data in fake mode (default: 5)
- `USE_FAKE_DATA` — Set to `true` for fake data generation, `false` for real microphone input with ML client classification (default: `true`)
- `FLASK_APP` — Flask application entry point (default: `app.py`)
- `FLASK_ENV` — Flask environment (default: `development`)

## Development Setup

Run this once if you don't have pipenv installed:
```bash
python -m pip install --upgrade pip
python -m pip install pipenv
```

## Before submitting a PR

Set up the development environment:
```bash
cd web-app
pipenv sync --dev
```

Run linting checks:
```bash
pipenv run pylint **/*.py
```

Run code formatting check:
```bash
pipenv run black --diff --check .
```

To auto-format code:
```bash
pipenv run black .
```

Run tests:
```bash
pipenv run pytest
```

Run tests with coverage:
```bash
pipenv run pytest --cov
```
## Troubleshooting

### App does not start / containers exit immediately

- Check logs:
  ```bash
  docker-compose logs web-app
  docker-compose logs ml-client
  docker-compose logs mongo
  ```

- Ensure `.env` exists:
  ```bash
  cp .env.example .env
  ```

- Restart everything:
  ```bash
  docker-compose down
  docker-compose up --build
  ```

### Cannot access http://localhost:5000/

- Confirm services are running:
  ```bash
  docker-compose ps
  ```
- Ensure port `5000` is not being used by another process.

### Microphone not working

- Set `USE_FAKE_DATA=false` in `.env`
- Allow microphone permissions in the browser
- Try using Chrome — some browsers block microphone access on localhost

### No data appears in dashboard

- If using fake data:
  ```bash
  docker-compose logs ml-client
  ```
- For real microphone mode:
  - Click “Start Microphone”
  - Check browser permissions

### Tests or lint failing

- Reinstall dev dependencies:
  ```bash
  pipenv sync --dev
  ```
- Auto-format:
  ```bash
  pipenv run black .
  ```
- Run test suite:
  ```bash
  pipenv run pytest
  ```