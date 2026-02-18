#!/bin/sh
# Lexecon startup: run migrations then start the API server.
set -e

DATA_DIR="${LEXECON_DATA_DIR:-.}"
AUTH_DB="${DATA_DIR}/lexecon_auth.db"

echo "[start] data dir: ${DATA_DIR}"
mkdir -p "${DATA_DIR}"

echo "[start] running migrations against ${AUTH_DB}..."
python /app/migrations/run_all.py "${AUTH_DB}"

echo "[start] starting uvicorn on port ${PORT:-8000}..."
exec python -m uvicorn lexecon.api.server:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${LEXECON_WORKERS:-1}"
