#!/bin/bash
# Double-click this file to launch vision.poker
# (Make sure to run: chmod +x run.command first)

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the app
python3 app.py
