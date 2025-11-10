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