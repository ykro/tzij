#!/usr/bin/env bash
# Training runtime: a Cloud Run Job with one NVIDIA L4 GPU (serverless, billed per second, same
# container image as the rest of the pipeline, nothing to keep running between monthly retrains).
#
# Creates or updates the job `${APP}-train` in ${TRAIN_REGION}. Each run is started by
# `make train` (train/submit_job.py) with `gcloud run jobs execute --args=...`.
#   IMAGE=... infra/03-train-job.sh     (IMAGE defaults to the output of 02-train-image.sh)
source "$(dirname "$0")/env.sh"

JOB="${APP}-train"
SA_EMAIL="${APP}-train@${PROJECT_ID}.iam.gserviceaccount.com"
STAGING_BUCKET="${STAGING_BUCKET:-gs://${PROJECT_ID}-train-eu}"
IMAGE="${IMAGE:-$(bash "$INFRA_DIR/02-train-image.sh")}"

# GPU jobs: tasks may run at most 1 h. L4 minimums on Cloud Run: 4 vCPU / 16 GiB. We use 8 / 32 GiB: loading, merging and converting a
# 5B-parameter checkpoint is CPU- and RAM-heavy. Cloud Run's filesystem lives in memory, so the
# base weights (~10 GB, read once) go to a Cloud Storage volume at /mnt/work
# in the same region as the GPU (cached for the next retrain). The merged model and the GGUFs go to the
# in-memory disk: the converter does many small random reads and writes that a bucket mount handles
# at ~3 MB/s. The merged model is deleted once converted to keep peak memory under 32 GiB.
say "Cloud Run Job ${JOB} (${TRAIN_REGION}, 1x L4)"
verb=(create)
exists gcloud run jobs describe "$JOB" --region "$TRAIN_REGION" && verb=(update --clear-volumes --clear-volume-mounts)
gcloud run jobs "${verb[@]}" "$JOB" \
  --region "$TRAIN_REGION" \
  --image "$IMAGE" \
  --gpu 1 --gpu-type nvidia-l4 --no-gpu-zonal-redundancy \
  --cpu 8 --memory 32Gi \
  --task-timeout 1h --max-retries 0 --tasks 1 \
  --service-account "$SA_EMAIL" \
  --add-volume "name=work,type=cloud-storage,bucket=${STAGING_BUCKET#gs://}" \
  --add-volume-mount "volume=work,mount-path=/mnt/work" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},CACHE_DIR=/mnt/work/${APP}/base-cache,OUT_DIR=/tmp/out,MERGED_DIR=/tmp/merged,DROP_MERGED=1,GGUF_OUTTYPE=${GGUF_OUTTYPE:-f16}" \
  --quiet
echo "$JOB"
