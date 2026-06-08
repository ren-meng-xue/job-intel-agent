#!/bin/bash
set -e

# Start Celery worker in background
uv run celery -A app.tasks:celery_app worker --loglevel=info &
CELERY_PID=$!

# Start uvicorn in foreground; when it exits, kill celery too
trap "kill $CELERY_PID 2>/dev/null" EXIT
uv run uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
