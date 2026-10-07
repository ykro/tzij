#!/usr/bin/env bash
# Shared settings for every infra script. Source it: `source infra/env.sh`.
# APP must be set by the repo's infra/app.env before sourcing this file.
set -euo pipefail

INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
[ -f "$INFRA_DIR/app.env" ] && source "$INFRA_DIR/app.env"

# A key missing from an older .env comes from .env.example.
dotenv() {
  local root value; root="$(cd "$INFRA_DIR/.." && pwd)"
  [ -f "$root/.env" ] && value="$(sed -n -E "s/^$1=(.*)$/\1/p" "$root/.env" | tail -1)"
  [ -n "${value:-}" ] || value="$(sed -n -E "s/^$1=(.*)$/\1/p" "$root/.env.example" | tail -1)"
  printf '%s\n' "$value"
}

# The project comes from .env (GOOGLE_CLOUD_PROJECT): to reproduce in your own project, change it there.
export PROJECT_ID="${PROJECT_ID:-$(dotenv GOOGLE_CLOUD_PROJECT)}"
export REGION="${REGION:-us-central1}"
export TRAIN_REGION="${TRAIN_REGION:-europe-west4}"
export CLOUDSDK_CORE_PROJECT="$PROJECT_ID"   # scope gcloud without touching the global config
export AR_REPO="${AR_REPO:-charlas2027}"
export AR="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}"
: "${APP:?set APP in infra/app.env}"

say() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
exists() { "$@" >/dev/null 2>&1; }

# deploy_run <service> <source-dir> [extra gcloud run deploy flags...]
# Builds with Cloud Build into Artifact Registry and deploys to Cloud Run.
deploy_run() {
  local service="$1" src="$2"; shift 2
  local image="${AR}/${service}:$(date +%Y%m%d-%H%M%S)"
  say "Building ${service} from ${src}"
  gcloud builds submit "$src" --tag "$image" --region "$REGION" --quiet
  say "Deploying ${service}"
  gcloud run deploy "$service" --image "$image" --region "$REGION" --quiet "$@"
  gcloud run services describe "$service" --region "$REGION" --format='value(status.url)'
}

# The demo: David's GPU service and the page, both next to the L4 quota (Cloud Run GPUs without
# zonal redundancy are available to this project in europe-west4).
export DEMO_REGION="${DEMO_REGION:-europe-west4}"
# Images of the demo live next to it: a cold start reads David's ~6 GB image from the same region.
export DEMO_AR="${DEMO_REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}"
export DAVID_SERVICE="${DAVID_SERVICE:-${APP}-david}"
export PAGE_SERVICE="${PAGE_SERVICE:-${APP}}"

# dotenv <KEY>: a value from .env (or .env.example), for the few settings the deploy scripts need.
