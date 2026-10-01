"""Run the LoRA fine-tune in the cloud, wait, and record how long it took and what it cost.

    python train/submit_job.py --app genlingo --tag genlingo-2027-03 --data data/train/chat.jsonl

Default runtime: a **Cloud Run Job with one NVIDIA L4** (infra/03-train-job.sh). Serverless,
billed per second while the task runs, and the same container image as everything else: nothing
stays up between monthly retrains. Alternative: `TRAIN_RUNTIME=vertex` submits the same container
as a Vertex AI Custom Job.

Steps: upload the chat JSONL to the staging bucket (same region as the GPU), build/reuse the
training image (Cloud Build, cached by content hash), run it, poll until it finishes, then write
train/runs/<tag>.json with duration, machine and cost. That file is what the talk shows:
"retraining David this month took N minutes and cost $X".

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
VERTEX_TERMINAL = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}

# Cloud Run instance-based billing (jobs), Tier 1 region, NVIDIA L4 without zonal redundancy.
# USD per second; override with env vars if the price list changes.
CLOUD_RUN_RATES = {
    "gpu_l4": float(os.environ.get("CLOUD_RUN_L4_USD_PER_S", "0.0001867")),
    "vcpu": float(os.environ.get("CLOUD_RUN_VCPU_USD_PER_S", "0.000018")),
    "gib": float(os.environ.get("CLOUD_RUN_GIB_USD_PER_S", "0.000002")),
}
CLOUD_RUN_SHAPE = {"vcpu": 8, "gib": 32}  # must match infra/03-train-job.sh


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


def train_args(args, data_uri: str, work_dir: str | None = None) -> list[str]:
    out = [
        f"--data={data_uri}",
        f"--tag={args.tag}",
        f"--base-model={env('GEMMA_BASE_MODEL')}",
        f"--weights-uri={env('GEMMA_WEIGHTS_URI')}",
        f"--output-uri={env('MODELS_BUCKET')}",
    ]
    if work_dir:
        out.append(f"--work-dir={work_dir}")
    return out + list(args.extra)


# ---- Cloud Run Job (default) -------------------------------------------------------------------
def cloud_run_cost(duration_s: float) -> float:
    per_s = CLOUD_RUN_RATES["gpu_l4"] + CLOUD_RUN_SHAPE["vcpu"] * CLOUD_RUN_RATES["vcpu"] + CLOUD_RUN_SHAPE["gib"] * CLOUD_RUN_RATES["gib"]
    return duration_s * per_s


def run_cloud_run(args, image: str, data_uri: str, region: str, run: dict, out: Path) -> dict:
    job = f"{args.app}-train"
    print(f"==> Cloud Run Job {job} ({region}, 1x L4)", flush=True)
    subprocess.run(["bash", str(REPO / "infra" / "03-train-job.sh")], check=True, stdout=subprocess.DEVNULL, env={**os.environ, "IMAGE": image})
    # Bulky files live on the Cloud Storage volume (Cloud Run's own filesystem is in memory).
    work_dir = f"/mnt/work/{args.app}/runs/{args.tag}"
    execution = sh(
        "gcloud", "run", "jobs", "execute", job, f"--region={region}", "--async",
        f"--args={','.join(train_args(args, data_uri, work_dir))}", "--format=value(metadata.name)",
    )
    print(f"==> execution {execution}", flush=True)
    run.update(runtime="cloud-run-job", job=job, execution=execution,
               machine=f"Cloud Run Job: 1x NVIDIA L4 (no zonal redundancy), {CLOUD_RUN_SHAPE['vcpu']} vCPU, {CLOUD_RUN_SHAPE['gib']} GiB",
               rates_usd_per_s=CLOUD_RUN_RATES)
    out.write_text(json.dumps(run, indent=2) + "\n")
    if args.no_wait:
        return run
    last = None
    while True:
        ex = json.loads(sh("gcloud", "run", "jobs", "executions", "describe", execution, f"--region={region}", "--format=json"))
        st = ex.get("status", {})
        cond = {c["type"]: c for c in st.get("conditions", [])}.get("Completed", {})
        state = "SUCCEEDED" if st.get("succeededCount") else "FAILED" if st.get("failedCount") or cond.get("status") == "False" else "RUNNING" if st.get("runningCount") else "PENDING"
        if state != last:
            print(f"    {time.strftime('%H:%M:%S')} {state}", flush=True)
            last = state
        if state in {"SUCCEEDED", "FAILED"} and st.get("completionTime"):
            break
        time.sleep(30)
    start, end = parse_time(st.get("startTime")), parse_time(st.get("completionTime"))
    duration_s = (end - start).total_seconds() if start and end else None
    run.update(
        state=f"JOB_STATE_{state}",
        start_time=st.get("startTime"),
        end_time=st.get("completionTime"),
        # The GPU instance is billed for its whole lifecycle ≈ execution start -> completion.
        duration_s=round(duration_s, 1) if duration_s else None,
        estimated_cost_usd=round(cloud_run_cost(duration_s), 2) if duration_s else None,
        error=cond.get("message") if state == "FAILED" else None,
    )
    return run


# ---- Vertex AI Custom Job (alternative) --------------------------------------------------------
def vertex_spec(args, image: str, data_uri: str, sa: str) -> dict:
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
                    "args": train_args(args, data_uri),
                    "env": [{"name": "GOOGLE_CLOUD_PROJECT", "value": env("GOOGLE_CLOUD_PROJECT")}],
                },
            }
        ],
        "serviceAccount": sa,
        "scheduling": {"strategy": env("TRAIN_SCHEDULING", "STANDARD")},  # SPOT = preemptible, cheaper
    }


def run_vertex(args, image: str, data_uri: str, region: str, project: str, run: dict, out: Path) -> dict:
    sa = f"{args.app}-train@{project}.iam.gserviceaccount.com"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(vertex_spec(args, image, data_uri, sa), fh)
        spec_path = fh.name
    try:
        name = sh("gcloud", "ai", "custom-jobs", "create", f"--project={project}", f"--region={region}",
                  f"--display-name={args.tag}", f"--config={spec_path}", "--format=value(name)")
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.stderr)
    hourly = float(env("TRAIN_HOURLY_USD", "0"))
    run.update(runtime="vertex-custom-job", job_id=name.rsplit("/", 1)[-1], job_name=name, hourly_usd=hourly,
               machine=f"{env('TRAIN_MACHINE', 'g2-standard-8')} + 1x {env('TRAIN_ACCELERATOR', 'NVIDIA_L4')} ({env('TRAIN_SCHEDULING', 'STANDARD').lower()})")
    out.write_text(json.dumps(run, indent=2) + "\n")
    print(f"==> Vertex AI job {run['job_id']} submitted in {region}", flush=True)
    if args.no_wait:
        return run
    last = None
    while True:
        job = json.loads(sh("gcloud", "ai", "custom-jobs", "describe", name, f"--region={region}", "--format=json"))
        state = job.get("state")
        if state != last:
            print(f"    {time.strftime('%H:%M:%S')} {state}", flush=True)
            last = state
        if state in VERTEX_TERMINAL:
            break
        time.sleep(30)
    start, end = parse_time(job.get("startTime")), parse_time(job.get("endTime"))
    duration_s = (end - start).total_seconds() if start and end else None
    run.update(state=state, start_time=job.get("startTime"), end_time=job.get("endTime"),
               duration_s=round(duration_s, 1) if duration_s else None,
               estimated_cost_usd=round(duration_s / 3600 * hourly, 2) if duration_s else None,
               error=(job.get("error") or {}).get("message"))
    return run


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--data", required=True, help="local chat JSONL")
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("extra", nargs="*", help="extra args for train_lora.py (after --)")
    args = ap.parse_args()

    project, region = env("GOOGLE_CLOUD_PROJECT"), env("TRAIN_REGION", "europe-west4")
    runtime = env("TRAIN_RUNTIME", "cloud-run")
    staging = env("STAGING_BUCKET").rstrip("/")
    data_uri = f"{staging}/{args.app}/data/{args.tag}/train.jsonl"
    n_examples = sum(1 for line in Path(args.data).read_text().splitlines() if line.strip())

    print(f"==> uploading {n_examples} examples to {data_uri}", flush=True)
    sh("gcloud", "storage", "cp", args.data, data_uri, "--quiet")
    print("==> training image (Cloud Build, cached by content hash)", flush=True)
    image = sh("bash", str(REPO / "infra" / "02-train-image.sh")).splitlines()[-1]

    runs_dir = REPO / "train" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    out = runs_dir / f"{args.tag}.json"
    run = {
        "tag": args.tag,
        "app": args.app,
        "where": "cloud",
        "region": region,
        "image": image,
        "base_model": env("GEMMA_BASE_MODEL"),
        "weights_uri": env("GEMMA_WEIGHTS_URI"),
        "data_uri": data_uri,
        "data_date": (m.group(0) if (m := re.search(r"\d{4}-\d{2}$", args.tag)) else None),
        "examples": n_examples,
        "output_uri": f"{env('MODELS_BUCKET').rstrip('/')}/{args.tag}/",
        "state": "PENDING",
    }
    if runtime == "vertex":
        run = run_vertex(args, image, data_uri, region, project, run, out)
    else:
        run = run_cloud_run(args, image, data_uri, region, run, out)
    if args.no_wait:
        return

    if run["state"].endswith("SUCCEEDED"):
        try:
            run["metrics"] = json.loads(sh("gcloud", "storage", "cat", f"{run['output_uri']}metrics.json"))
        except subprocess.CalledProcessError:
            pass
    out.write_text(json.dumps(run, indent=2) + "\n")
    print(json.dumps({k: run.get(k) for k in ("tag", "state", "duration_s", "estimated_cost_usd")}), flush=True)
    if not run["state"].endswith("SUCCEEDED"):
        sys.exit(1)


if __name__ == "__main__":
    main()
