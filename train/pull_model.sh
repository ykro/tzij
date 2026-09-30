#!/usr/bin/env bash
# Download a trained David from GCS and register it in the local Ollama.
#   train/pull_model.sh genlingo-2027-03        # Q4_K_M -> ollama model "genlingo-2027-03"
#   FP16=1 train/pull_model.sh genlingo-2027-03 # also f16 -> "genlingo-2027-03-f16" (for the eval)
set -euo pipefail
TAG="${1:?usage: pull_model.sh <tag>}"
BUCKET="${MODELS_BUCKET:?set MODELS_BUCKET (gs://...)}"
DIR="$(cd "$(dirname "$0")/.." && pwd)/models/${TAG}"
mkdir -p "$DIR"

files=("${BUCKET}/${TAG}/Modelfile" "${BUCKET}/${TAG}/${TAG}-q4_k_m.gguf" "${BUCKET}/${TAG}/metrics.json")
[ "${FP16:-0}" = 1 ] && files+=("${BUCKET}/${TAG}/Modelfile.f16" "${BUCKET}/${TAG}/${TAG}-f16.gguf")
gcloud storage cp "${files[@]}" "$DIR/"   # skips nothing, but GCS -> laptop is the only network step

cd "$DIR"
ollama create "$TAG" -f Modelfile
[ "${FP16:-0}" = 1 ] && ollama create "${TAG}-f16" -f Modelfile.f16
ollama list | grep -E "^${TAG}(-f16)?[: ]" || true
