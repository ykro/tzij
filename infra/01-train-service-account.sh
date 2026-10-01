#!/usr/bin/env bash
# Service account for the Vertex AI training job, with access only to what training needs:
# read the training data (staging bucket), write models (models bucket), pull the image.
# Base weights come from Hugging Face (hf://google) with the hf-token secret, cached in the staging bucket.
source "$(dirname "$0")/env.sh"

SA="${APP}-train"
SA_EMAIL="${SA}@${PROJECT_ID}.iam.gserviceaccount.com"
MODELS_BUCKET="${MODELS_BUCKET:-gs://${PROJECT_ID}-${APP}-models}"
STAGING_BUCKET="${STAGING_BUCKET:-gs://${PROJECT_ID}-train-eu}"

say "Service account ${SA_EMAIL}"
exists gcloud iam service-accounts describe "$SA_EMAIL" \
  || gcloud iam service-accounts create "$SA" --display-name="${APP} training job"

say "Bucket access"
gcloud storage buckets add-iam-policy-binding "$MODELS_BUCKET" \
  --member="serviceAccount:${SA_EMAIL}" --role=roles/storage.objectAdmin --quiet >/dev/null
gcloud storage buckets add-iam-policy-binding "$STAGING_BUCKET" \
  --member="serviceAccount:${SA_EMAIL}" --role=roles/storage.objectAdmin --quiet >/dev/null

say "Artifact Registry read (${AR_REPO})"
gcloud artifacts repositories add-iam-policy-binding "$AR_REPO" --location="$REGION" \
  --member="serviceAccount:${SA_EMAIL}" --role=roles/artifactregistry.reader --quiet >/dev/null

# Only needed if GEMMA_WEIGHTS_URI=hf://google (gated Hugging Face weights).
if exists gcloud secrets describe hf-token; then
  say "Secret hf-token"
  gcloud secrets add-iam-policy-binding hf-token \
    --member="serviceAccount:${SA_EMAIL}" --role=roles/secretmanager.secretAccessor --quiet >/dev/null
fi
echo "$SA_EMAIL"
