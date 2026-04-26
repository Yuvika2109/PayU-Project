#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Fraud Rule Engine – Quick Start Script
# Usage: ./start.sh [model]
#   model defaults to llama3.2:3b
# ─────────────────────────────────────────────────────────────────────────────

set -e

MODEL="${1:-llama3.2:3b}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "  🛡️  Fraud Rule Engine – Quick Start"
echo "  ─────────────────────────────────────"
echo ""

# ── Check Ollama ──────────────────────────────────────────────────────────────
echo "  [1/5] Checking Ollama..."
if ! command -v ollama &> /dev/null; then
  echo "  ❌ Ollama not found. Install from https://ollama.com"
  exit 1
fi

if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
  echo "  ⚠️  Ollama not running. Starting it..."
  ollama serve &
  sleep 3
fi

echo "  ✅ Ollama running"

# ── Pull model ────────────────────────────────────────────────────────────────
echo ""
echo "  [2/5] Checking model: $MODEL"
if ! ollama list 2>/dev/null | grep -q "$MODEL"; then
  echo "  ⬇️  Pulling $MODEL (this may take a few minutes)..."
  ollama pull "$MODEL"
else
  echo "  ✅ Model $MODEL already available"
fi

# ── Backend setup ─────────────────────────────────────────────────────────────
echo ""
echo "  [3/5] Setting up backend..."
cd "$SCRIPT_DIR/backend"

if [ ! -f .env ]; then
  cp .env.example .env
  # Update model in .env
  sed -i.bak "s/OLLAMA_MODEL=.*/OLLAMA_MODEL=$MODEL/" .env && rm -f .env.bak
  echo "  ✅ Created .env with model=$MODEL"
fi

if [ ! -d ".venv" ]; then
  echo "  Creating Python virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt
echo "  ✅ Backend dependencies installed"

# ── Start backend ─────────────────────────────────────────────────────────────
echo ""
echo "  [4/5] Starting backend on http://localhost:8000..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
sleep 2

# ── Frontend setup ────────────────────────────────────────────────────────────
echo ""
echo "  [5/5] Setting up and starting frontend..."
cd "$SCRIPT_DIR/frontend"

if [ ! -d "node_modules" ]; then
  npm install
fi

echo ""
echo "  ─────────────────────────────────────────────────────"
echo "  ✅  Fraud Rule Engine is ready!"
echo ""
echo "     Frontend  →  http://localhost:3000"
echo "     API Docs  →  http://localhost:8000/docs"
echo "     Model     →  $MODEL"
echo "  ─────────────────────────────────────────────────────"
echo ""

# Trap to kill backend when frontend exits
cleanup() {
  echo ""
  echo "  Shutting down..."
  kill $BACKEND_PID 2>/dev/null || true
}
trap cleanup EXIT

npm run dev
