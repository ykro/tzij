"""Second half of a fine-tune: LoRA adapter -> merge -> GGUF (f16 + quantized) -> Modelfile -> bucket.

Runs as its own Cloud Run Job (CPU only, `${APP}-finish`), right after the GPU job that trains the
adapter (`${APP}-train`, `ADAPTER_ONLY=1`). `make train` chains both; `make train-finish` runs this
same code on a laptop as a fallback (finish_local.py).

    python finish.py --tag tzij-2026-10 --adapter-uri /mnt/work/tzij/runs/tzij-2026-10/adapter \
        --base-model $GEMMA_BASE_MODEL --weights-uri $GEMMA_WEIGHTS_URI --ollama-renderer $OLLAMA_RENDERER \
        --quant Q5_K_M --keep-f16 --output-uri gs://ai-experiments-487722-tzij-models

Why a separate job: Cloud Run's local filesystem lives in the instance's memory. Training, a 10 GB
merged checkpoint and a 9 GB f16 GGUF don't fit together in 32 GiB. Here nothing else is in memory:
  - the base weights are copied from the bucket mount to local disk (LOCAL_BASE_DIR) with one
    sequential read, and deleted as soon as they're loaded: memory-mapped page faults over the
    mount ran at ~5 MB/s;
  - the merge runs in a child process, so its ~10 GB of tensors are returned when it exits;
  - the merged checkpoint goes to the in-memory disk (the converter reads it tensor by tensor);
  - the f16 GGUF goes to an ephemeral disk volume (F16_DIR, disk-backed, not memory);
  - the merged checkpoint is deleted before quantizing.
Peak ≈ 20 GiB, and no GPU is billed while it runs.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import train_lora  # noqa: E402
from train_lora import log  # noqa: E402


# What this stage adds to metrics.json (the rest comes from the training job).
FINISH_KEYS = ("where_merged", "quant", "download_s", "merge_s", "gguf_f16", "gguf_quant", "f16_bytes", "quant_bytes",
               "gguf_s", "finish_s", "publish_s")


def _merge(base_dir: str, adapter: str, merged_dir: str, drop_base_weights: bool = False) -> None:
    """W' = W + (alpha/r)·B·A, saved as an ordinary checkpoint (child process: its RAM goes back on exit)."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(base_dir, dtype=torch.bfloat16, low_cpu_mem_usage=True)
    if drop_base_weights:  # a temporary copy on the in-memory disk: free it before writing the merged one
        for f in Path(base_dir).glob("*.safetensors"):
            f.unlink()
    merged = PeftModel.from_pretrained(model, adapter).merge_and_unload()
    merged.save_pretrained(merged_dir, safe_serialization=True)
    for f in Path(base_dir).iterdir():  # tokenizer, chat template, processor config (same rule as train_lora)
        if f.is_file() and not f.name.endswith(train_lora.WEIGHT_SUFFIXES) and f.name not in {"config.json", "model.safetensors.index.json"}:
            shutil.copy2(f, Path(merged_dir) / f.name)


def finish(*, tag: str, adapter_uri: str, base_model: str, weights_uri: str, renderer: str, work: Path, out: Path,
           f16_dir: Path | None = None, cache_dir: Path | None = None, local_base_dir: Path | None = None,
           quant: str, keep_f16: bool = False,
           llama_cpp: Path, output_uri: str = "", where: str = "cloud-run", temperature: float = 0.2) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    f16_dir = f16_dir or out
    f16_dir.mkdir(parents=True, exist_ok=True)
    metrics: dict = {"where_merged": where, "quant": quant}
    t_all = time.time()

    if not os.environ.get("HF_TOKEN"):
        token = train_lora.hf_token_from_secret_manager(os.environ.get("GOOGLE_CLOUD_PROJECT"))
        if token:
            os.environ["HF_TOKEN"] = token

    t0 = time.time()
    adapter = train_lora.fetch(adapter_uri, work / "adapter")
    base_dir = train_lora.base_weights(base_model, weights_uri, cache_dir or work / "base")
    if local_base_dir:  # the cache is a bucket mount: copy it locally with one sequential read, because
        # loading memory-maps the weights and page faults over the mount crawl (~5 MB/s)
        local = local_base_dir / base_model
        shutil.copytree(base_dir, local, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".cache"))
        base_dir = local
    metrics["download_s"] = round(time.time() - t0, 1)

    t0 = time.time()
    merged_dir = work / "merged"
    child = mp.get_context("spawn").Process(target=_merge, args=(str(base_dir), str(adapter), str(merged_dir), bool(local_base_dir)))
    child.start()
    child.join()
    if child.exitcode != 0:
        raise SystemExit(f"merge failed (exit code {child.exitcode})")
    metrics["merge_s"] = round(time.time() - t0, 1)
    log(f"merged in {metrics['merge_s']}s")
    if local_base_dir:
        shutil.rmtree(local_base_dir / base_model, ignore_errors=True)

    metrics.update(train_lora.to_gguf(merged_dir, out, tag, llama_cpp, quant, drop_merged=True, outtype="f16", f16_dir=f16_dir))
    f16 = f16_dir / metrics["gguf_f16"]
    if keep_f16:  # published as the uncompressed reference for the compression eval
        train_lora.write_modelfile(out, metrics["gguf_f16"], renderer, temperature)
    else:
        f16.unlink(missing_ok=True)
        metrics["gguf_f16"] = None
    train_lora.write_modelfile(out, metrics["gguf_quant"], renderer, temperature)
    metrics["finish_s"] = round(time.time() - t_all, 1)

    if output_uri:
        dest = f"{output_uri.rstrip('/')}/{tag}"
        t0 = time.time()
        train_lora.publish(out, dest)
        if keep_f16 and f16_dir != out:
            train_lora.publish(f16_dir, dest, only=[f16.name])
        metrics["publish_s"] = round(time.time() - t0, 1)
        metrics = merge_metrics(dest, out, metrics)
    else:
        (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    log(json.dumps(metrics))
    return metrics


def merge_metrics(dest: str, out: Path, finish_metrics: dict) -> dict:
    """The training job already wrote metrics.json next to the model: add the finish stage to it."""
    existing: dict = {}
    if dest.startswith("gs://"):
        bucket, prefix = train_lora._split_gs(dest)
        blob = train_lora._gcs().bucket(bucket).blob(f"{prefix}/metrics.json")
        if blob.exists():
            existing = json.loads(blob.download_as_text())
    merged = {**existing, **finish_metrics}
    (out / "metrics.json").write_text(json.dumps(merged, indent=2) + "\n")
    train_lora.publish(out, dest, only=["metrics.json"])
    return merged


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    env = os.environ.get
    ap = argparse.ArgumentParser(description="LoRA adapter -> merge -> GGUF -> Modelfile -> GCS")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--adapter-uri", required=True, help="adapter dir: local/volume path or gs:// prefix")
    ap.add_argument("--base-model", default=env("GEMMA_BASE_MODEL"), required=not env("GEMMA_BASE_MODEL"))
    ap.add_argument("--weights-uri", default=env("GEMMA_WEIGHTS_URI"), required=not env("GEMMA_WEIGHTS_URI"))
    ap.add_argument("--ollama-renderer", default=env("OLLAMA_RENDERER"), required=not env("OLLAMA_RENDERER"))
    ap.add_argument("--output-uri", default=env("MODELS_BUCKET", ""))
    ap.add_argument("--work-dir", default=env("WORK_DIR", "/tmp/finish"))
    ap.add_argument("--out-dir", default=env("OUT_DIR", ""))
    ap.add_argument("--f16-dir", default=env("F16_DIR", ""), help="where the f16 GGUF is written (a disk volume on Cloud Run)")
    ap.add_argument("--cache-dir", default=env("CACHE_DIR", ""))
    ap.add_argument("--local-base-dir", default=env("LOCAL_BASE_DIR", ""),
                    help="copy the cached base weights here before loading (when the cache is a bucket mount); deleted once loaded")
    ap.add_argument("--quant", default=env("QUANT"), required=not env("QUANT"),
                    help="GGUF quantization, e.g. Q5_K_M (env QUANT; no default: it is a decision from the quant sweep)")
    ap.add_argument("--keep-f16", action="store_true", default=env("KEEP_F16", "") == "1")
    ap.add_argument("--llama-cpp", default=env("LLAMA_CPP_DIR", "/opt/llama.cpp"))
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    work = Path(args.work_dir)
    return finish(
        tag=args.tag, adapter_uri=args.adapter_uri, base_model=args.base_model, weights_uri=args.weights_uri,
        renderer=args.ollama_renderer, work=work, out=Path(args.out_dir) if args.out_dir else work / "out",
        f16_dir=Path(args.f16_dir) if args.f16_dir else None, cache_dir=Path(args.cache_dir) if args.cache_dir else None,
        local_base_dir=Path(args.local_base_dir) if args.local_base_dir else None,
        quant=args.quant, keep_f16=args.keep_f16, llama_cpp=Path(args.llama_cpp), output_uri=args.output_uri,
    )


if __name__ == "__main__":
    main()
