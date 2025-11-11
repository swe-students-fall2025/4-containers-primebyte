![Lint-free](https://github.com/nyu-software-engineering/containerized-app-exercise/actions/workflows/lint.yml/badge.svg)

# Containerized App Exercise

Build a containerized app that uses machine learning. See [instructions](./instructions.md) for details.

# SoundWatch

Day 1 setup: a simple Flask web app and MongoDB running in containers.

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
- http://localhost:5000/api/health (should check health)

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