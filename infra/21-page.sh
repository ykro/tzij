#!/usr/bin/env bash
# The demo page on Cloud Run (public): David and Goliath side by side. Its service account may call
# David's private service and Gemini on Vertex AI, nothing else. Idempotent.
source "$(dirname "$0")/env.sh"

SA="${APP}-page"
SA_EMAIL="${SA}@${PROJECT_ID}.iam.gserviceaccount.com"
ROOT="$(cd "$INFRA_DIR/.." && pwd)"
IMAGE="${DEMO_AR}/${PAGE_SERVICE}:$(date +%Y%m%d-%H%M%S)"
DAVID_URL="$(gcloud run services describe "$DAVID_SERVICE" --region "$DEMO_REGION" --format='value(status.url)')"
[ -n "$DAVID_URL" ] || { echo "!! ${DAVID_SERVICE} is not deployed: run infra/20-david.sh first"; exit 1; }

say "Service account ${SA_EMAIL}"
exists gcloud iam service-accounts describe "$SA_EMAIL" \
  || gcloud iam service-accounts create "$SA" --display-name="${APP} demo page"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:${SA_EMAIL}" \
  --role roles/aiplatform.user --condition=None --quiet >/dev/null
gcloud run services add-iam-policy-binding "$DAVID_SERVICE" --region "$DEMO_REGION" \
  --member "serviceAccount:${SA_EMAIL}" --role roles/run.invoker --quiet >/dev/null

say "Building ${IMAGE}"
gcloud builds submit "$ROOT" --config "$ROOT/page/cloudbuild.yaml" --region "$DEMO_REGION" --quiet \
  --substitutions "_IMAGE=${IMAGE}"

say "Deploying ${PAGE_SERVICE} (${DEMO_REGION}, public)"
gcloud run deploy "$PAGE_SERVICE" --image "$IMAGE" --region "$DEMO_REGION" --service-account "$SA_EMAIL" \
  --cpu 1 --memory 1Gi --min-instances 0 --max-instances 3 --timeout 300 \
  --allow-unauthenticated --quiet \
  --set-env-vars "DAVID_URL=${DAVID_URL},GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
# The page reads David's shape and prices, and Gemini's, from .env.example (baked into its image).
gcloud run services describe "$PAGE_SERVICE" --region "$DEMO_REGION" --format='value(status.url)'
