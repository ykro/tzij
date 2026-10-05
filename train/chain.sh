#!/usr/bin/env bash
# Train in chunks: one Cloud Run GPU job per shard (a job lasts at most 1 h), each continuing the previous adapter.
#   train/chain.sh <tag-prefix> <data.jsonl> <first-shard> <last-shard> <n-shards> <init-tag> [extra train_lora args]
#   train/chain.sh tzij-2026-10-mix data/train/chat-raft-bt-both-dst2409-new30.jsonl 0 7 8 tzij-2026-10-tm-a-e2-s4 --seed=2031
# Writes train/runs/<prefix>-s<i>.json per shard; then: make train-finish TAG=<prefix>-s<last>.
set -u
prefix=$1 data=$2 first=$3 last=$4 n=$5 prev=$6
shift 6
cd "$(dirname "$0")/.."
# .env as defaults (ABLATION_STEPS has characters bash can't source; it's only for evals)
envf=$(mktemp); grep -v "^ABLATION_STEPS" .env > "$envf"; set -a; . "$envf"; set +a; rm -f "$envf"
for i in $(seq "$first" "$last"); do
  tag="$prefix-s$i"
  echo "== shard $i/$n -> $tag (from $prev)"
  uv run --project duel python train/submit_job.py --app tzij --tag "$tag" --data "$data" -- \
    --shard="$i/$n" --init-adapter="$STAGING_BUCKET/tzij/runs/$prev/adapter" "$@" || { echo "== FAILED $tag"; exit 1; }
  prev=$tag
done
echo "== DONE $prefix (last $prev)"
