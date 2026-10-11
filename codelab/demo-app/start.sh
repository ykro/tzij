#!/usr/bin/env bash
set -euo pipefail

export OLLAMA_HOST="127.0.0.1:11434"
export OLLAMA_MODELS="/models"
export OLLAMA_KEEP_ALIVE="-1"
export OLLAMA_URL="http://127.0.0.1:11434"
export GEMMA_MODEL="${GEMMA_MODEL:-gemma4:e2b}"
export PORT="${PORT:-8080}"

ollama serve >/tmp/ollama.log 2>&1 &

exec node /app/server.mjs
