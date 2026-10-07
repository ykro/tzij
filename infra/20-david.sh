#!/usr/bin/env bash
# David's GPU service on Cloud Run (private): the fine-tuned Gemma + EmbeddingGemma in Ollama, the
# retrieval index and MBR decoding, on one NVIDIA L4. Idempotent: rebuilds the image and redeploys.
#
#   min-instances 0: nothing is billed while nobody uses the page. Opening the page wakes it.
#   max-instances 1: one GPU is enough for a talk.
# The image (~6 GB) carries the model files, so a cold start reads nothing from the internet. Three
# steps: build the image; run it once as a Cloud Run Job on an L4 (david/warm_cache.py) so CUDA
# compiles its GPU kernels and saves them; build the final image with those kernels and deploy it.
# Without the kernels a cold start took about 3.5 minutes; with them, see README (David en la nube).
source "$(dirname "$0")/env.sh"

SA="${APP}-david"
SA_EMAIL="${SA}@${PROJECT_ID}.iam.gserviceaccount.com"
MODEL_TAG="${MODEL_TAG:-$(dotenv LOCAL_MODEL_TAG)}"
MODELS_BUCKET="${MODELS_BUCKET:-$(dotenv MODELS_BUCKET)}"
DATA_BUCKET="${DATA_BUCKET_URI:-$(dotenv DATA_BUCKET_URI)}"
DATASET="${DATASET:-$(gcloud storage cat "${DATA_BUCKET}/datasets/LATEST" | tr -d '[:space:]')}"
STAMP="${MODEL_TAG}-$(date +%Y%m%d-%H%M%S)"
BASE_IMAGE="${DEMO_AR}/${DAVID_SERVICE}:${STAMP}-base"
IMAGE="${DEMO_AR}/${DAVID_SERVICE}:${STAMP}"
CPU="$(dotenv DAVID_CPU)"; MEMORY="$(dotenv DAVID_MEMORY_GIB)Gi"
STAGING_BUCKET="${STAGING_BUCKET:-gs://${PROJECT_ID}-train-eu}"
CACHE_URI="${STAGING_BUCKET}/${APP}/david-cache/${STAMP}/cuda-cache.tgz"
WARM_JOB="${DAVID_SERVICE}-warm"
WARM_SA="${APP}-train@${PROJECT_ID}.iam.gserviceaccount.com"   # may write the staging bucket
ROOT="$(cd "$INFRA_DIR/.." && pwd)"

say "Service account ${SA_EMAIL} (no access to anything: David only answers the page)"
exists gcloud iam service-accounts describe "$SA_EMAIL" \
  || gcloud iam service-accounts create "$SA" --display-name="${APP} David (GPU service)"

gcloud storage ls "${DATA_BUCKET}/index/${DATASET}/tzij.sqlite" >/dev/null \
  || { echo "!! Missing ${DATA_BUCKET}/index/${DATASET}/tzij.sqlite: run make index"; exit 1; }

say "Building ${BASE_IMAGE} (${MODEL_TAG}, index of dataset ${DATASET})"
gcloud builds submit "$ROOT" --config "$ROOT/david/cloudbuild.yaml" --region "$DEMO_REGION" --quiet \
  --substitutions "_IMAGE=${BASE_IMAGE},_MODEL_TAG=${MODEL_TAG},_MODELS_BUCKET=${MODELS_BUCKET},_DATA_BUCKET=${DATA_BUCKET},_DATASET=${DATASET},_EMBEDDING_MODEL=$(dotenv EMBEDDING_MODEL)"

say "Compiling the GPU kernels once on an L4 (${WARM_JOB}) -> ${CACHE_URI}"
JOB_FLAGS=(--image "$BASE_IMAGE" --region "$DEMO_REGION" --service-account "$WARM_SA"
  --gpu 1 --gpu-type nvidia-l4 --no-gpu-zonal-redundancy --cpu "$CPU" --memory "$MEMORY"
  --task-timeout 30m --max-retries 0 --command /opt/venv/bin/python --args /warm_cache.py
  --set-env-vars "CACHE_URI=${CACHE_URI},LOCAL_MODEL_TAG=${MODEL_TAG},PYTHONPATH=/app:/app/duel" --quiet)
if exists gcloud run jobs describe "$WARM_JOB" --region "$DEMO_REGION"; then
  gcloud run jobs update "$WARM_JOB" "${JOB_FLAGS[@]}"
else
  gcloud run jobs create "$WARM_JOB" "${JOB_FLAGS[@]}"
fi
gcloud run jobs execute "$WARM_JOB" --region "$DEMO_REGION" --wait --quiet

say "Building ${IMAGE} (base + compiled kernels)"
gcloud builds submit "$ROOT/david" --config "$ROOT/david/cloudbuild-cache.yaml" --region "$DEMO_REGION" --quiet \
  --substitutions "_BASE=${BASE_IMAGE},_IMAGE=${IMAGE},_CACHE_URI=${CACHE_URI}"

say "Deploying ${DAVID_SERVICE} (${DEMO_REGION}, 1x L4)"
gcloud run deploy "$DAVID_SERVICE" --image "$IMAGE" --region "$DEMO_REGION" --service-account "$SA_EMAIL" \
  --gpu 1 --gpu-type nvidia-l4 --no-gpu-zonal-redundancy \
  --cpu "$CPU" --memory "$MEMORY" --no-cpu-throttling --cpu-boost \
  --min-instances 0 --max-instances 1 --concurrency 16 --timeout 300 \
  --no-allow-unauthenticated --quiet \
  --set-env-vars "LOCAL_MODEL_TAG=${MODEL_TAG},DAVID_MBR=1"
gcloud run services describe "$DAVID_SERVICE" --region "$DEMO_REGION" --format='value(status.url)'
