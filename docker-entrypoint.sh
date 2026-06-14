#!/usr/bin/env bash
set -e

mkdir -p /app/data

echo "Running database migrations..."
uv run --no-dev reflex db migrate

echo "Starting Linen Draper..."
exec uv run --no-dev reflex run \
    --env prod \
    --backend-host 0.0.0.0 \
    --backend-port 3000 \
    --loglevel info
