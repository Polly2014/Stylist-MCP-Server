#!/bin/bash
# =============================================================================
# Stylist MCP Server - One-Click Setup Script
# =============================================================================

set -e

echo "========================================"
echo "  Stylist MCP Server Setup"
echo "========================================"
echo ""

# Check Python version
echo "Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is required but not found"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "  Python version: $PYTHON_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo ""
    echo "Creating .env from template..."
    cp .env.example .env
    echo "  ⚠️  Please edit .env to configure your paths!"
fi

# Create data directory if needed
if [ ! -d "data" ]; then
    mkdir -p data
    echo "Created data/ directory"
fi

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env to configure paths (DRESSCODE_ROOT, CHROMADB_PATH)"
echo "  2. Build ChromaDB index (if not already done):"
echo "     python scripts/build_chromadb.py"
echo "  3. Run the MCP server:"
echo "     # stdio mode (for Claude Desktop)"
echo "     python src/mcp_server.py"
echo ""
echo "     # SSE mode (for remote access)"
echo "     python src/mcp_server.py --sse --port 8080"
echo ""
