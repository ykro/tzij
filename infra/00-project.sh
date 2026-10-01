#!/usr/bin/env bash
# Everything Tzij needs in a Google Cloud project, from scratch. Idempotent: safe to rerun.
#   APIs, the Artifact Registry repo, the data/models/staging buckets and the hf-token secret.
# Run once per project (make deploy runs it first). Needs Owner or Editor on the project.
source "$(dirname "$0")/env.sh"

DATA_BUCKET="${DATA_BUCKET_URI:-gs://${PROJECT_ID}-tzij-data}"
MODELS_BUCKET="${MODELS_BUCKET:-gs://${PROJECT_ID}-tzij-models}"
STAGING_BUCKET="${STAGING_BUCKET:-gs://${PROJECT_ID}-train-eu}"

say "APIs"
gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  storage.googleapis.com secretmanager.googleapis.com aiplatform.googleapis.com \
  iam.googleapis.com logging.googleapis.com --quiet

say "Artifact Registry repo ${AR_REPO} (${REGION})"
exists gcloud artifacts repositories describe "$AR_REPO" --location "$REGION" \
  || gcloud artifacts repositories create "$AR_REPO" --repository-format=docker --location "$REGION" \
       --description "Container images for the 2027 talk demos" --quiet

bucket() { # bucket <gs://name> <location>: the data never leaves the project; uniform access, no public ACLs
  exists gcloud storage buckets describe "$1" \
    || gcloud storage buckets create "$1" --location "$2" --uniform-bucket-level-access --public-access-prevention --quiet
}
say "Buckets"
bucket "$DATA_BUCKET" "$REGION"           # pipeline raw cache + versioned datasets
bucket "$MODELS_BUCKET" "$REGION"         # fine-tuned GGUFs pulled to the laptop
bucket "$STAGING_BUCKET" "$TRAIN_REGION"  # training data + base-weight cache, next to the GPU

say "Secret hf-token (gated BOUQuET, Gemma weights)"
if exists gcloud secrets describe hf-token; then
  echo "hf-token exists"
elif [ -n "${HF_TOKEN:-}" ]; then
  printf %s "$HF_TOKEN" | gcloud secrets create hf-token --data-file=- --replication-policy=automatic --quiet
else
  echo "!! hf-token missing. Create it with your Hugging Face read token (after accepting the BOUQuET terms):"
  echo "   HF_TOKEN=hf_... bash infra/00-project.sh"
fi
