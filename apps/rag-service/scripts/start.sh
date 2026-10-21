#!/usr/bin/env bash
# Start the x-QingChuan application

set -e

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Create data directories if they don't exist
mkdir -p data/chroma data/documents logs

# Check if .env exists
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "Please edit .env and add your API keys."
fi

# Activate virtual environment and run
uv run uvicorn qingchuan_rag.main:app --host 0.0.0.0 --port 8010 --reload
