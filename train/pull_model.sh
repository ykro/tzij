#!/usr/bin/env bash
# Download a trained David from GCS and register it in the local Ollama.
#   train/pull_model.sh tzij-2026-10-mix-s7   # whatever GGUF its Modelfile points to
set -euo pipefail
TAG="${1:?usage: pull_model.sh <tag>}"
BUCKET="${MODELS_BUCKET:?set MODELS_BUCKET (gs://...)}"
DIR="$(cd "$(dirname "$0")/.." && pwd)/models/${TAG}"
mkdir -p "$DIR"
cd "$DIR"

gcloud storage cp "${BUCKET}/${TAG}/Modelfile" .
GGUF="$(sed -n 's|^FROM \./||p' Modelfile)"   # the Modelfile names the GGUF it needs
[ -f "$GGUF" ] || gcloud storage cp "${BUCKET}/${TAG}/${GGUF}" .
gcloud storage cp "${BUCKET}/${TAG}/metrics.json" . 2>/dev/null || true
ollama create "$TAG" -f Modelfile

ollama list | grep -E "^${TAG}[: ]" || true
