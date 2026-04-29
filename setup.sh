#!/bin/bash
set -e

echo "=== IRAC Maker Setup ==="

# Check ollama
if ! command -v ollama &>/dev/null; then
  echo "Ollama not found. Install it first: https://ollama.com/download"
  exit 1
fi

# Pull base model if needed (must match the FROM line in Modelfile)
echo "Checking qwen3.5:9b..."
ollama pull qwen3.5:9b

# Create custom irac-maker model
echo "Building irac-maker model..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ollama create irac-maker -f "$SCRIPT_DIR/Modelfile"

# Install Python deps
echo "Installing Python dependencies..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt

echo ""
echo "Setup complete. Run the app with:"
echo "  source .venv/bin/activate"
echo "  streamlit run app.py"
