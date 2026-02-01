#!/bin/bash
# Start both API and Worker in a single container
# This saves costs on Railway by using only one service

set -e

echo "Starting YouTube Downloader..."
echo "Storage mode: ${STORAGE_MODE:-local}"

# Start worker in background
echo "Starting worker..."
uv run rq worker --url "$REDIS_URL" &
WORKER_PID=$!

# Start API server in foreground
echo "Starting API server on port ${PORT:-8000}..."
exec uv run uvicorn ytdl.main:app --host 0.0.0.0 --port "${PORT:-8000}"
