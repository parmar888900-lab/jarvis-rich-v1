#!/usr/bin/env bash
set -e

echo "=== JARVIS AI Setup ==="

if [ ! -d "venv" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv venv
fi

echo "Installing Python dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo "Installing frontend dependencies..."
cd frontend && npm install && cd ..

echo ""
echo "Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Install Ollama: https://ollama.com/download"
echo "  2. Pull a model:    ollama pull llama3.2"
echo "  3. Start backend:   cd backend && ../venv/bin/python -m uvicorn app:app --reload"
echo "  4. Start frontend:  cd frontend && npm run dev"
