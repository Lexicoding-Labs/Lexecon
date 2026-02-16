#!/bin/bash
# Lexecon Server Startup Script

echo "🚀 Starting Lexecon Governance API..."
echo ""

# Navigate to project directory
cd /Users/air/Lexecon

# Activate virtual environment
echo "✓ Activating virtual environment..."
source .venv/bin/activate

# Load environment variables
if [ -f .env ]; then
    echo "✓ Loading .env file..."
    export $(cat .env | grep -v '^#' | xargs)
fi

# Start the server
echo "✓ Starting uvicorn server..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Server will be available at:"
echo "   http://localhost:8000"
echo ""
echo "📚 Interactive API docs:"
echo "   http://localhost:8000/docs"
echo ""
echo "🛑 Press Ctrl+C to stop the server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

uvicorn lexecon.api.server:app --reload --host 0.0.0.0 --port 8000
