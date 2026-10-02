#!/usr/bin/env bash
# Builds the training image with Cloud Build (no local Docker/GPU needed). The tag is a hash of
# the build inputs, so an unchanged recipe is never rebuilt. Prints the image URI.
source "$(dirname "$0")/env.sh"
TRAIN_DIR="$(cd "$INFRA_DIR/../train" && pwd)"
HASH="$(cat "$TRAIN_DIR/Dockerfile" "$TRAIN_DIR/requirements.txt" "$TRAIN_DIR/train_lora.py" "$TRAIN_DIR/finish.py" | shasum -a 256 | cut -c1-12)"
IMAGE="${AR}/${APP}-train:${HASH}"
if exists gcloud artifacts docker images describe "$IMAGE"; then
  echo "$IMAGE"; exit 0
fi
say "Building ${IMAGE} (Cloud Build, ~15 min the first time)" >&2
gcloud builds submit "$TRAIN_DIR" --tag "$IMAGE" --region "$REGION" --machine-type=e2-highcpu-8 --timeout=3600s --quiet >&2
echo "$IMAGE"
