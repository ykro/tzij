#!/usr/bin/env bash
# Training runtime: two Cloud Run Jobs from the same image, chained by `make train` (train/submit_job.py).
#
#   ${APP}-train   1x NVIDIA L4. LoRA fine-tune; saves the adapter to the Cloud Storage volume and stops
#                  (ADAPTER_ONLY=1).
#   ${APP}-finish  CPU only. Adapter -> merge -> GGUF f16 + quantized -> Modelfile -> models bucket
#                  (train/finish.py).
#
# Why two jobs: Cloud Run's filesystem lives in the instance's memory (32 GiB here). Training plus a
# 10 GB merged checkpoint plus a 9 GB f16 GGUF don't fit in one instance. Split, each half fits:
# the GPU job only holds the model it trains, and the finish job merges in a child process, writes
# the f16 GGUF to an ephemeral disk volume (disk-backed, max 10 GiB per instance) and drops the merged
# checkpoint before quantizing. Bonus: the GPU isn't billed while merging and converting.
#
# Base weights (~10 GB, read once) are cached on a Cloud Storage volume at /mnt/work in the GPU
# region, shared by both jobs and by next month's retrain.
#   IMAGE=... infra/03-train-job.sh     (IMAGE defaults to the output of 02-train-image.sh)
source "$(dirname "$0")/env.sh"

SA_EMAIL="${APP}-train@${PROJECT_ID}.iam.gserviceaccount.com"
STAGING_BUCKET="${STAGING_BUCKET:-gs://${PROJECT_ID}-train-eu}"
IMAGE="${IMAGE:-$(bash "$INFRA_DIR/02-train-image.sh")}"
WORK_VOLUME=(--add-volume "name=work,type=cloud-storage,bucket=${STAGING_BUCKET#gs://}"
             --add-volume-mount "volume=work,mount-path=/mnt/work")
COMMON_ENV="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},CACHE_DIR=/mnt/work/${APP}/base-cache"

# upsert <job> <flags...>: create, or update replacing volumes (so the flags are the whole truth).
upsert() {
  local job="$1"; shift
  local verb=(create)
  exists gcloud run jobs describe "$job" --region "$TRAIN_REGION" && verb=(update --clear-volumes --clear-volume-mounts)
  gcloud run jobs "${verb[@]}" "$job" --region "$TRAIN_REGION" --image "$IMAGE" --service-account "$SA_EMAIL" \
    --max-retries 0 --tasks 1 --quiet "$@"
}

# GPU jobs: tasks may run at most 1 h. L4 minimums on Cloud Run: 4 vCPU / 16 GiB; 8 / 32 GiB loads the
# checkpoint faster and leaves room for the optimizer state.
say "Cloud Run Job ${APP}-train (${TRAIN_REGION}, 1x L4)"
upsert "${APP}-train" \
  --gpu 1 --gpu-type nvidia-l4 --no-gpu-zonal-redundancy \
  --cpu 8 --memory 32Gi --task-timeout 1h \
  "${WORK_VOLUME[@]}" \
  --set-env-vars "${COMMON_ENV},ADAPTER_ONLY=1"

# CPU job: base weights copied from the bucket mount to memory with one sequential read and freed once
# loaded (memory-mapped reads over the mount crawl), merged checkpoint in memory (~10 GB, read tensor
# by tensor by the converter), f16 GGUF on the ephemeral disk (~9 GB), quantized GGUF back in memory
# once the merged checkpoint is gone. Peak ≈ 20 GiB.
say "Cloud Run Job ${APP}-finish (${TRAIN_REGION}, CPU)"
upsert "${APP}-finish" \
  --cpu 8 --memory 32Gi --task-timeout 1h \
  --command "python,/app/finish.py" \
  "${WORK_VOLUME[@]}" \
  --add-volume "name=scratch,type=ephemeral-disk,size=10Gi" \
  --add-volume-mount "volume=scratch,mount-path=/mnt/scratch" \
  --set-env-vars "${COMMON_ENV},WORK_DIR=/tmp/finish,OUT_DIR=/tmp/out,LOCAL_BASE_DIR=/tmp/base,F16_DIR=/mnt/scratch"
echo "${APP}-train ${APP}-finish"
