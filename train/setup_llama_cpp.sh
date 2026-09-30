#!/usr/bin/env bash
# Local llama.cpp for `make train-local`: the HF -> GGUF converter (Python, from the pinned tag)
# and the prebuilt quantizer for this Mac. Same tag as the training image (Dockerfile).
set -euo pipefail
TAG="${LLAMA_CPP_TAG:-b11292}"
DIR="$(cd "$(dirname "$0")" && pwd)/.llama.cpp"
[ -x "$DIR/bin/llama-quantize" ] && [ -f "$DIR/convert_hf_to_gguf.py" ] && { echo "$DIR"; exit 0; }
rm -rf "$DIR" && git clone -q --depth 1 --branch "$TAG" https://github.com/ggml-org/llama.cpp "$DIR" >&2
mkdir -p "$DIR/bin"
curl -sL "https://github.com/ggml-org/llama.cpp/releases/download/${TAG}/llama-${TAG}-bin-macos-arm64.tar.gz" | tar xz -C "$DIR/bin" --strip-components=1
echo "$DIR"
