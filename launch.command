#!/bin/bash
cd "$(dirname "$0")"

# Activate venv if it exists, otherwise use system Python
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

# Open browser after a short delay
sleep 2 && open http://localhost:8501 &

streamlit run app.py
