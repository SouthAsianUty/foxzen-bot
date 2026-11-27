#!/bin/bash
cd "$(dirname "$0")"

echo "🦊 Starting Foxzen Bot & Web Admin..."

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
fi

echo "Opening Web Admin at http://localhost:8000"
.venv/bin/python main.py
