#!/usr/bin/env bash
# Vertex AI custom training needs its own GPU quota (separate from Compute Engine / Cloud Run).
# New projects start at 0 L4s for training, and `make train` fails with RESOURCE_EXHAUSTED.
# This files a quota request for 1 L4 in the training region; Google reviews it (minutes to days).
#   CONTACT_EMAIL=you@example.com infra/03-request-training-gpu-quota.sh
source "$(dirname "$0")/env.sh"
: "${CONTACT_EMAIL:?set CONTACT_EMAIL for the quota request}"

say "Current request status"
gcloud beta quotas preferences list --project="$PROJECT_ID" \
  --filter="quotaId=CustomModelTrainingL4GPUsPerProjectPerRegion" \
  --format='table(dimensions.region,quotaConfig.preferredValue,quotaConfig.grantedValue,quotaConfig.stateDetail)'

say "Requesting 1 NVIDIA L4 for Vertex AI training in ${TRAIN_REGION}"
gcloud beta quotas preferences create \
  --project="$PROJECT_ID" \
  --service=aiplatform.googleapis.com \
  --quota-id=CustomModelTrainingL4GPUsPerProjectPerRegion \
  --dimensions=region="$TRAIN_REGION" \
  --preferred-value=1 \
  --email="$CONTACT_EMAIL" \
  --justification="LoRA fine-tuning of a small Gemma model for a conference demo: one short job per month (~30 min)."
