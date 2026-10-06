#!/usr/bin/env bash
# David's GPU service on Cloud Run (private): the fine-tuned Gemma + EmbeddingGemma in Ollama, the
# retrieval index and MBR decoding, on one NVIDIA L4. Idempotent: rebuilds the image and redeploys.
#
#   min-instances 0: nothing is billed while nobody uses the page. Opening the page wakes it.
#   max-instances 1: one GPU is enough for a talk.
# The image (~6 GB) carries the model files, so a cold start reads nothing from the internet.
source "$(dirname "$0")/env.sh"

SA="${APP}-david"
SA_EMAIL="${SA}@${PROJECT_ID}.iam.gserviceaccount.com"
MODEL_TAG="${MODEL_TAG:-$(dotenv LOCAL_MODEL_TAG)}"
MODELS_BUCKET="${MODELS_BUCKET:-$(dotenv MODELS_BUCKET)}"
DATA_BUCKET="${DATA_BUCKET_URI:-$(dotenv DATA_BUCKET_URI)}"
DATASET="${DATASET:-$(gcloud storage cat "${DATA_BUCKET}/datasets/LATEST" | tr -d '[:space:]')}"
IMAGE="${AR}/${DAVID_SERVICE}:${MODEL_TAG}-$(date +%Y%m%d-%H%M%S)"
ROOT="$(cd "$INFRA_DIR/.." && pwd)"

say "Service account ${SA_EMAIL} (no access to anything: David only answers the page)"
exists gcloud iam service-accounts describe "$SA_EMAIL" \
  || gcloud iam service-accounts create "$SA" --display-name="${APP} David (GPU service)"

gcloud storage ls "${DATA_BUCKET}/index/${DATASET}/tzij.sqlite" >/dev/null \
  || { echo "!! Missing ${DATA_BUCKET}/index/${DATASET}/tzij.sqlite: run make index"; exit 1; }

say "Building ${IMAGE} (${MODEL_TAG}, index of dataset ${DATASET})"
gcloud builds submit "$ROOT" --config "$ROOT/david/cloudbuild.yaml" --region "$DEMO_REGION" --quiet \
  --substitutions "_IMAGE=${IMAGE},_MODEL_TAG=${MODEL_TAG},_MODELS_BUCKET=${MODELS_BUCKET},_DATA_BUCKET=${DATA_BUCKET},_DATASET=${DATASET},_EMBEDDING_MODEL=$(dotenv EMBEDDING_MODEL)"

say "Deploying ${DAVID_SERVICE} (${DEMO_REGION}, 1x L4)"
gcloud run deploy "$DAVID_SERVICE" --image "$IMAGE" --region "$DEMO_REGION" --service-account "$SA_EMAIL" \
  --gpu 1 --gpu-type nvidia-l4 --no-gpu-zonal-redundancy \
  --cpu 8 --memory 32Gi --no-cpu-throttling \
  --min-instances 0 --max-instances 1 --concurrency 8 --timeout 300 \
  --no-allow-unauthenticated --quiet \
  --set-env-vars "LOCAL_MODEL_TAG=${MODEL_TAG},DAVID_MBR=1"
gcloud run services describe "$DAVID_SERVICE" --region "$DEMO_REGION" --format='value(status.url)'
