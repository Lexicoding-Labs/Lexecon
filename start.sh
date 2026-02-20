#!/bin/sh
# Lexecon startup: run migrations then start the API server.
set -e

echo "======================================"
echo "Lexecon Startup Script"
echo "======================================"

# Get data directory
DATA_DIR="${LEXECON_DATA_DIR:-.}"
AUTH_DB="${DATA_DIR}/lexecon_auth.db"
PORT="${PORT:-8000}"

echo "[start] Environment:"
echo "  DATA_DIR: ${DATA_DIR}"
echo "  AUTH_DB: ${AUTH_DB}"
echo "  PORT: ${PORT}"
echo "  LEXECON_ENV: ${LEXECON_ENV:-not set}"
echo "  LEXECON_DATA_DIR: ${LEXECON_DATA_DIR:-not set}"
echo ""

# Create data directory
echo "[start] Creating data directory..."
mkdir -p "${DATA_DIR}" || {
    echo "ERROR: Failed to create data directory ${DATA_DIR}"
    exit 1
}
echo "  ✓ Data directory created"
echo ""

# Check Python
echo "[start] Python environment:"
python --version
echo "  PYTHONPATH: ${PYTHONPATH}"
echo ""

# Test imports with full error output
echo "[start] Testing Python imports..."
python -c "
import sys
print('  sys.path:', sys.path)
print('  Importing lexecon...')
import lexecon
print('  ✓ lexecon imported OK')
print('  Importing lexecon.api.server...')
from lexecon.api.server import app
print('  ✓ lexecon.api.server imported OK')
print('  Importing FastAPI...')
from fastapi import FastAPI
print('  ✓ All imports successful')
" 2>&1 || {
    echo "ERROR: Python import failed"
    exit 1
}
echo ""

# Run migrations
echo "[start] Running database migrations..."
echo "  Database path: ${AUTH_DB}"
python /app/migrations/run_all.py "${AUTH_DB}" 2>&1 || {
    echo "ERROR: Database migration failed"
    exit 1
}
echo ""

# Verify database files exist
echo "[start] Verifying database files:"
ls -la "${DATA_DIR}"/*.db 2>/dev/null || echo "  (no .db files yet)"
echo ""

# Start server
echo "[start] Starting uvicorn server..."
echo "  Host: 0.0.0.0"
echo "  Port: ${PORT}"
echo "  Workers: ${LEXECON_WORKERS:-1}"
echo "======================================"
echo ""

# Use exec to replace shell with uvicorn process
exec python -m uvicorn lexecon.api.server:app \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --workers "${LEXECON_WORKERS:-1}" \
    --log-level info \
    --access-log
