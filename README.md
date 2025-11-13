![Lint-free](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/lint.yml/badge.svg)

# Containerized App Exercise

Build a containerized app that uses machine learning. See [instructions](./instructions.md) for details.

# SoundWatch

SoundWatch continuously samples ambient audio, classifies each snippet into silent/quiet/normal/loud/very loud bands, and surfaces the history in a sleek Flask dashboard. MongoDB persists the decibel readings and labels so both the ML client and the web UI stay perfectly in sync across containers.

## Project Vision

Every N seconds the microphone-backed client records a short snippet, measures its loudness, and classifies it as silent, quiet, normal, loud, or very loud. Those snapshots get stored in MongoDB so the Flask web app can display real-time and historical charts of the noise environment. This pipeline satisfies the multi-container requirement while giving us clear milestones for sensor capture, analysis, storage, and visualization.

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
- http://localhost:5000/health (should check health)


## Web App Routes

- `/` — renders the dashboard UI.
- `/health` — lightweight health probe with status metadata.
- `/api/current` — returns the latest noise reading.
- `/api/stats` — exposes aggregate decibel stats.
- `/api/history` — supplies historical timestamps, levels, and labels.


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