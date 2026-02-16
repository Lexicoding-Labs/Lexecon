#!/bin/bash
# Lexecon Demo Run Script
# The ONE way to run the demo slice
# Starts the API server and serves the canonical dashboard

set -e

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$DEMO_DIR/.venv"
DEMO_ENV="$DEMO_DIR/.env.demo"

echo "🚀 Lexecon Demo"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Verify setup
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Error: Virtual environment not found"
    echo "   Run: ./scripts/demo-setup.sh"
    exit 1
fi

if [ ! -f "$DEMO_ENV" ]; then
    echo "❌ Error: Demo environment not found"
    echo "   Run: ./scripts/demo-setup.sh"
    exit 1
fi

# Check port availability
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "❌ Error: Port 8000 is already in use"
    echo "   Stop the existing server or change ports"
    exit 1
fi

# Activate environment and load demo config
echo "→ Activating demo environment..."
source "$VENV_DIR/bin/activate"
export $(cat "$DEMO_ENV" | grep -v '^#' | xargs)

echo "✓ Environment loaded"
echo ""
echo "Starting server..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Demo will be available at:"
echo "   http://localhost:8000"
echo ""
echo "📊 Canonical Dashboard:"
echo "   http://localhost:8000/dashboard"
echo ""
echo "📚 API Documentation:"
echo "   http://localhost:8000/docs"
echo ""
echo "🔍 Core Flow to Test:"
echo "   1. Issue capability"
echo "   2. Make decision (policy evaluation)"
echo "   3. View ledger proof"
echo ""
echo "🛑 Press Ctrl+C to stop"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start the server
cd "$DEMO_DIR"
exec uvicorn lexecon.api.server:app --host 0.0.0.0 --port 8000 --no-access-log
