#!/usr/bin/env bash
# Download a trained David from GCS and register it in the local Ollama.
#   train/pull_model.sh tzij-2026-10-raft-bt-s3   # whatever GGUF its Modelfile points to
#   FP16=1 train/pull_model.sh tzij-2026-10-raft-bt-s3 # also <tag>-f16 (for the eval)
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

if [ "${FP16:-0}" = 1 ]; then
  gcloud storage cp "${BUCKET}/${TAG}/Modelfile.f16" .
  F16="$(sed -n 's|^FROM \./||p' Modelfile.f16)"
  [ -f "$F16" ] || gcloud storage cp "${BUCKET}/${TAG}/${F16}" .
  ollama create "${TAG}-f16" -f Modelfile.f16
fi
ollama list | grep -E "^${TAG}(-f16)?[: ]" || true
