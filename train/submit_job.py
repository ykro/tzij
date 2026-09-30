"""Submit the LoRA fine-tune as a Vertex AI Custom Job, wait, and record what it cost.

    python train/submit_job.py --app genlingo --tag genlingo-2027-03 --data data/train/chat.jsonl

Steps: upload the chat JSONL to the staging bucket (same region as the GPU), build/reuse the
training image (Cloud Build), create the job on one L4, poll until it finishes, then write
train/runs/<tag>.json with duration, machine and estimated cost. That file is what the talk
shows: "retraining David this month took N minutes and cost $X".

Only needs the gcloud CLI (no SDK), so it runs anywhere gcloud is authenticated.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TERMINAL = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}


def sh(*cmd: str, capture: bool = True) -> str:
    res = subprocess.run(cmd, check=True, text=True, capture_output=capture)
    return res.stdout.strip() if capture else ""


def env(name: str, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if val in (None, ""):
        sys.exit(f"missing env var {name} (see .env.example)")
    return val


def parse_time(ts: str | None) -> datetime | None:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def job_spec(args, image: str, data_uri: str, sa: str) -> dict:
    return {
        "workerPoolSpecs": [
            {
                "machineSpec": {
                    "machineType": env("TRAIN_MACHINE", "g2-standard-8"),
                    "acceleratorType": env("TRAIN_ACCELERATOR", "NVIDIA_L4"),
                    "acceleratorCount": 1,
                },
                "replicaCount": 1,
                "diskSpec": {"bootDiskType": "pd-ssd", "bootDiskSizeGb": 200},  # base + merged + 2 GGUFs
                "containerSpec": {
                    "imageUri": image,
                    "args": [
                        f"--data={data_uri}",
                        f"--tag={args.tag}",
                        f"--base-model={env('GEMMA_BASE_MODEL')}",
                        f"--weights-uri={env('GEMMA_WEIGHTS_URI')}",
                        f"--output-uri={env('MODELS_BUCKET')}",
                        *args.extra,
                    ],
                    "env": [{"name": "GOOGLE_CLOUD_PROJECT", "value": env("GOOGLE_CLOUD_PROJECT")}],
                },
            }
        ],
        "serviceAccount": sa,
        # SPOT uses the (much more available) preemptible GPU quota at a lower price; a preempted
        # job is restarted by Vertex. STANDARD = on-demand.
        "scheduling": {"strategy": env("TRAIN_SCHEDULING", "STANDARD")},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--data", required=True, help="local chat JSONL")
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("extra", nargs="*", help="extra args for train_lora.py (after --)")
    args = ap.parse_args()

    project, region = env("GOOGLE_CLOUD_PROJECT"), env("TRAIN_REGION", "europe-west4")
    staging = env("STAGING_BUCKET").rstrip("/")
    data_uri = f"{staging}/{args.app}/data/{args.tag}/train.jsonl"
    n_examples = sum(1 for line in Path(args.data).read_text().splitlines() if line.strip())

    print(f"==> uploading {n_examples} examples to {data_uri}", flush=True)
    sh("gcloud", "storage", "cp", args.data, data_uri, "--quiet")
    print("==> training image (Cloud Build, cached by content hash)", flush=True)
    image = sh("bash", str(REPO / "infra" / "02-train-image.sh")).splitlines()[-1]
    sa = f"{args.app}-train@{project}.iam.gserviceaccount.com"

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(job_spec(args, image, data_uri, sa), fh)
        spec_path = fh.name
    try:
        name = sh(
            "gcloud", "ai", "custom-jobs", "create", f"--project={project}", f"--region={region}",
            f"--display-name={args.tag}", f"--config={spec_path}", "--format=value(name)",
        )
    except subprocess.CalledProcessError as exc:
        if "quota" in (exc.stderr or "").lower():
            sys.exit(
                f"No Vertex AI training GPU quota in {region} ({env('TRAIN_ACCELERATOR', 'NVIDIA_L4')}).\n"
                "Request it with infra/03-request-training-gpu-quota.sh, or train on this Mac with `make train-local`."
            )
        sys.exit(exc.stderr)
    job_id = name.rsplit("/", 1)[-1]
    print(f"==> job {job_id} submitted in {region}", flush=True)
    print(f"    https://console.cloud.google.com/vertex-ai/training/custom-jobs?project={project}", flush=True)
    runs_dir = REPO / "train" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run = {
        "tag": args.tag,
        "app": args.app,
        "job_id": job_id,
        "job_name": name,
        "region": region,
        "machine": f"{env('TRAIN_MACHINE', 'g2-standard-8')} + 1x {env('TRAIN_ACCELERATOR', 'NVIDIA_L4')} ({env('TRAIN_SCHEDULING', 'STANDARD').lower()})",
        "image": image,
        "base_model": env("GEMMA_BASE_MODEL"),
        "data_uri": data_uri,
        "data_date": (m.group(0) if (m := re.search(r"\d{4}-\d{2}$", args.tag)) else None),
        "examples": n_examples,
        "output_uri": f"{env('MODELS_BUCKET').rstrip('/')}/{args.tag}/",
        "hourly_usd": float(env("TRAIN_HOURLY_USD", "0")),
        "state": "JOB_STATE_PENDING",
    }
    out = runs_dir / f"{args.tag}.json"
    out.write_text(json.dumps(run, indent=2) + "\n")
    if args.no_wait:
        return

    last = None
    while True:
        job = json.loads(sh("gcloud", "ai", "custom-jobs", "describe", name, f"--region={region}", "--format=json"))
        state = job.get("state")
        if state != last:
            print(f"    {time.strftime('%H:%M:%S')} {state}", flush=True)
            last = state
        if state in TERMINAL:
            break
        time.sleep(30)

    start, end = parse_time(job.get("startTime")), parse_time(job.get("endTime"))
    duration_s = (end - start).total_seconds() if start and end else None
    run.update(
        state=state,
        create_time=job.get("createTime"),
        start_time=job.get("startTime"),
        end_time=job.get("endTime"),
        duration_s=round(duration_s, 1) if duration_s else None,
        # Billed time ≈ time the machine ran (start → end). Estimate, not an invoice.
        estimated_cost_usd=round(duration_s / 3600 * run["hourly_usd"], 2) if duration_s else None,
        error=(job.get("error") or {}).get("message"),
    )
    if state == "JOB_STATE_SUCCEEDED":
        try:
            run["metrics"] = json.loads(sh("gcloud", "storage", "cat", f"{run['output_uri']}metrics.json"))
        except subprocess.CalledProcessError:
            pass
    out.write_text(json.dumps(run, indent=2) + "\n")
    print(json.dumps({k: run.get(k) for k in ("tag", "state", "duration_s", "estimated_cost_usd")}), flush=True)
    if state != "JOB_STATE_SUCCEEDED":
        sys.exit(1)


if __name__ == "__main__":
    main()
