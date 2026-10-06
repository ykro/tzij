#!/usr/bin/env bash
# Finish an E4B fine-tune in the cloud: adapter -> merge -> GGUF -> Modelfile -> models bucket.
#   infra/04-finish-batch.sh <tag> [OUTPUT_URI=gs://...]     (make train-finish TAG=<tag>)
#
# Why Cloud Batch and not the ${APP}-finish Cloud Run Job: Gemma 4 E4B's merged checkpoint is 16 GB,
# and a Cloud Run instance keeps its files in its own memory (32 GiB at most). A Batch job runs the
# same training image (same finish.py) on one VM with 64 GB of RAM and a 200 GB disk, and the VM is
# deleted when the task ends. Billed per second, nothing stays up.
source "$(dirname "$0")/env.sh"

TAG="${1:?usage: infra/04-finish-batch.sh <tag>}"
SA_EMAIL="${APP}-train@${PROJECT_ID}.iam.gserviceaccount.com"
STAGING_BUCKET="${STAGING_BUCKET:-$(dotenv STAGING_BUCKET)}"; STAGING_BUCKET="${STAGING_BUCKET:-gs://${PROJECT_ID}-train-eu}"
OUTPUT_URI="${OUTPUT_URI:-$(dotenv MODELS_BUCKET)}"
IMAGE="${IMAGE:-$(bash "$INFRA_DIR/02-train-image.sh")}"
JOB="${APP}-finish-$(echo "$TAG" | tr '[:upper:]_.' '[:lower:]--')-$(date +%H%M%S)"
JOB="${JOB:0:62}"

gcloud services enable batch.googleapis.com --quiet
for role in roles/batch.agentReporter roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:${SA_EMAIL}" --role "$role" \
    --condition=None --quiet >/dev/null
done
gcloud storage ls "${STAGING_BUCKET}/${APP}/runs/${TAG}/adapter/adapter_config.json" >/dev/null \
  || { echo "!! No adapter at ${STAGING_BUCKET}/${APP}/runs/${TAG}/adapter/"; exit 1; }

CONFIG="$(mktemp)"
cat > "$CONFIG" <<JSON
{
  "taskGroups": [{
    "taskSpec": {
      "runnables": [{
        "container": {
          "imageUri": "${IMAGE}",
          "entrypoint": "python",
          "commands": ["/app/finish.py", "--tag", "${TAG}",
                       "--adapter-uri", "${STAGING_BUCKET}/${APP}/runs/${TAG}/adapter",
                       "--output-uri", "${OUTPUT_URI}",
                       "--work-dir", "/tmp/finish", "--out-dir", "/tmp/out", "--f16-dir", "/tmp/f16",
                       "--local-base-dir", "/tmp/base", "--cache-dir", "/mnt/disks/work/${APP}/base-cache"],
          "volumes": ["/mnt/disks/work:/mnt/disks/work"]
        }
      }],
      "volumes": [{"gcs": {"remotePath": "${STAGING_BUCKET#gs://}"}, "mountPath": "/mnt/disks/work"}],
      "environment": {"variables": {
        "GOOGLE_CLOUD_PROJECT": "${PROJECT_ID}",
        "GEMMA_BASE_MODEL": "$(dotenv GEMMA_BASE_MODEL)",
        "GEMMA_WEIGHTS_URI": "$(dotenv GEMMA_WEIGHTS_URI)",
        "OLLAMA_RENDERER": "$(dotenv OLLAMA_RENDERER)",
        "QUANT": "$(dotenv QUANT)"
      }},
      "computeResource": {"cpuMilli": 8000, "memoryMib": 61440},
      "maxRunDuration": "7200s",
      "maxRetryCount": 0
    },
    "taskCount": 1
  }],
  "allocationPolicy": {
    "location": {"allowedLocations": ["regions/${TRAIN_REGION}"]},
    "instances": [{"policy": {"machineType": "n2-highmem-8", "bootDisk": {"sizeGb": 200, "type": "pd-balanced"}}}],
    "serviceAccount": {"email": "${SA_EMAIL}"}
  },
  "logsPolicy": {"destination": "CLOUD_LOGGING"}
}
JSON

say "Cloud Batch job ${JOB} (${TRAIN_REGION}, n2-highmem-8, 200 GB disk)"
gcloud batch jobs submit "$JOB" --location "$TRAIN_REGION" --config "$CONFIG" --quiet >/dev/null
rm -f "$CONFIG"
start=$(date +%s)
while :; do
  state="$(gcloud batch jobs describe "$JOB" --location "$TRAIN_REGION" --format='value(status.state)')"
  case "$state" in SUCCEEDED|FAILED|CANCELLED) break ;; esac
  sleep 30
done
secs=$(( $(date +%s) - start ))
echo "${JOB}: ${state} in $((secs / 60)) min"
echo "Logs: gcloud logging read 'labels.job_uid=\"$(gcloud batch jobs describe "$JOB" --location "$TRAIN_REGION" --format='value(uid)')\"' --limit 50"
[ "$state" = SUCCEEDED ] && gcloud storage ls "${OUTPUT_URI}/${TAG}/"
[ "$state" = SUCCEEDED ]
