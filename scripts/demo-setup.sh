#!/bin/bash
# Lexecon Demo Setup Script
# One-command setup for the deterministic demo slice
# This script creates the environment, installs deps, and prepares the data directory

set -e

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$DEMO_DIR/.venv"
DATA_DIR="$DEMO_DIR/data"
DEMO_ENV="$DEMO_DIR/.env.demo"

echo "🔧 Lexecon Demo Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is required"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
REQUIRED_VERSION="3.9"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Error: Python $REQUIRED_VERSION+ required, found $PYTHON_VERSION"
    exit 1
fi

echo "✓ Python $PYTHON_VERSION detected"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "→ Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment exists"
fi

# Activate and install dependencies
echo "→ Installing dependencies from pyproject.toml..."
source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -e "$DEMO_DIR"
echo "✓ Dependencies installed"

# Create data directory for SQLite databases
echo "→ Initializing data directory..."
mkdir -p "$DATA_DIR"
# Remove any committed database files to ensure clean state
rm -f "$DATA_DIR"/*.db 2>/dev/null || true
echo "✓ Data directory ready: $DATA_DIR"

# Generate minimal demo environment file
echo "→ Creating demo environment configuration..."

# Generate deterministic demo keys (32 bytes = 64 hex chars)
DEMO_MASTER_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DEMO_DB_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DEMO_SESSION_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

cat > "$DEMO_ENV" << EOF
# Lexecon Demo Environment
# Generated automatically by demo-setup.sh
# These keys are for demo purposes only - regenerate for production

LEXECON_ENV=demo
LEXECON_NODE_ID=demo-node
LEXECON_DATA_DIR=$DATA_DIR
LEXECON_LOG_LEVEL=INFO
LEXECON_LOG_FORMAT=text
LEXECON_POLICY_MODE=strict

# Cryptographic Keys (demo-only)
LEXECON_MASTER_KEY=$DEMO_MASTER_KEY
DB_ENCRYPTION_KEY=$DEMO_DB_KEY
SESSION_SECRET_KEY=$DEMO_SESSION_KEY

# Demo Configuration
LEXECON_RATE_LIMIT_ENABLED=false
LEXECON_BASE_URL=http://localhost:8000
EOF

echo "✓ Demo environment created: $DEMO_ENV"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Demo setup complete!"
echo ""
echo "Next step:"
echo "  ./scripts/demo-run.sh"
echo ""
echo "Then open: http://localhost:8000"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
