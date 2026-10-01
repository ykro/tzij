#!/usr/bin/env bash
# Data pipeline as a Cloud Run Job (make data-cloud).
#
# Why a job: the pipeline downloads ~1.5 GB (the Wiktionary dump is streamed and
# filtered), must be reproducible, and shouldn't depend on the presenter's laptop.
# It writes versioned datasets to gs://$DATA_BUCKET/datasets/<version>/ and keeps
# the raw download cache in gs://$DATA_BUCKET/raw/ (never in git).
#
# The Hugging Face token (Secret Manager `hf-token`) is mounted as HF_TOKEN: it
# unlocks the gated BOUQuET benchmark and avoids the 429s Hugging Face returns to
# anonymous downloads from Cloud Run IPs.
source "$(dirname "$0")/env.sh"

JOB="${APP}-data"
DATA_BUCKET="${DATA_BUCKET:-${PROJECT_ID}-tzij-data}"
SA_NAME="${APP}-data-job"
SA="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE="${AR}/${JOB}:$(date +%Y%m%d-%H%M%S)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

say "Service account ${SA_NAME} (read/write only on gs://${DATA_BUCKET})"
exists gcloud iam service-accounts describe "$SA" \
  || gcloud iam service-accounts create "$SA_NAME" --display-name "Tzij data pipeline job"
# A new service account takes a few seconds to become visible to IAM: retry.
for attempt in 1 2 3 4 5 6; do
  gcloud storage buckets add-iam-policy-binding "gs://${DATA_BUCKET}" \
    --member "serviceAccount:${SA}" --role roles/storage.objectAdmin --quiet >/dev/null && break
  [ "$attempt" = 6 ] && exit 1
  sleep 10
done

if exists gcloud secrets describe hf-token; then
  gcloud secrets add-iam-policy-binding hf-token --member "serviceAccount:${SA}" \
    --role roles/secretmanager.secretAccessor --quiet >/dev/null
  SECRETS=(--set-secrets "HF_TOKEN=hf-token:latest")
else
  echo "!! Secret hf-token not found: gated sources (BOUQuET) will be skipped."
  SECRETS=(--clear-secrets)
fi

say "Building ${IMAGE}"
gcloud builds submit "$ROOT" --config "$ROOT/pipeline/cloudbuild.yaml" \
  --substitutions "_IMAGE=${IMAGE}" --region "$REGION" --quiet

say "Deploying job ${JOB}"
gcloud run jobs deploy "$JOB" --image "$IMAGE" --region "$REGION" \
  --service-account "$SA" --cpu 2 --memory 4Gi --task-timeout 3600 --max-retries 0 "${SECRETS[@]}" \
  --set-env-vars "DATA_BUCKET_URI=gs://${DATA_BUCKET},GIT_SHA=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)" \
  --quiet

if [ "${DEPLOY_ONLY:-0}" = 1 ]; then
  echo "Deployed ${JOB} (not executed). Run it with: make data-cloud"
  exit 0
fi

say "Running ${JOB}"
gcloud run jobs execute "$JOB" --region "$REGION" --wait
echo "Latest dataset: $(gcloud storage cat "gs://${DATA_BUCKET}/datasets/LATEST")"
echo "Pull it locally with: make data-pull"
