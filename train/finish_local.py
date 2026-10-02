"""Finish a cloud fine-tune on this Mac: adapter (from the bucket) -> merge -> GGUF -> models bucket.

    make train-finish TAG=tzij-2026-09

Why this exists: the Cloud Run L4 job has 32 GiB of memory, and its filesystem lives in that same
memory. Gemma 4 E4B trains fine there (the LoRA adapter is saved to the Cloud Storage volume), but
merging a 16 GB checkpoint and converting it to GGUF does not fit. The laptop has 64 GB, so the
GPU-hungry part (training) runs in the cloud and the RAM-hungry part (merge + convert) runs here,
with the same functions train_lora.py uses. Output is identical: Modelfile + Q4_K_M GGUF +
metrics.json in gs://<MODELS_BUCKET>/<tag>/, so `make pull-model` doesn't care.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import train_lora  # noqa: E402


def main() -> None:
    tag = sys.argv[1]
    base_model = os.environ["GEMMA_BASE_MODEL"]
    weights_uri = os.environ.get("GEMMA_WEIGHTS_URI", "hf://google")
    staging = os.environ["STAGING_BUCKET"].rstrip("/")
    models = os.environ["MODELS_BUCKET"].rstrip("/")
    work_root = Path(os.environ.get("WORK_DIR", HERE.parent / "models" / ".work"))
    work = work_root / tag
    publish_model = "--no-publish" not in sys.argv  # ablation models: register in Ollama only
    out = HERE.parent / "models" / tag
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    metrics: dict = {"tag": tag, "base_model": base_model, "where_merged": "laptop"}

    if not os.environ.get("HF_TOKEN"):
        token = train_lora.hf_token_from_secret_manager(os.environ.get("GOOGLE_CLOUD_PROJECT"))
        if token:
            os.environ["HF_TOKEN"] = token

    t0 = time.time()
    adapter = train_lora.fetch(f"{staging}/tzij/runs/{tag}/adapter", work / "adapter")
    base_dir = train_lora.base_weights(base_model, weights_uri, work_root / "base")  # shared across tags
    metrics["download_s"] = round(time.time() - t0, 1)

    t0 = time.time()
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(base_dir, dtype=torch.bfloat16, low_cpu_mem_usage=True)
    merged = PeftModel.from_pretrained(model, adapter).merge_and_unload()
    merged_dir = work / "merged"
    merged.save_pretrained(merged_dir, safe_serialization=True)
    for f in base_dir.iterdir():  # tokenizer, chat template, processor config (same rule as train_lora)
        if f.is_file() and not f.name.endswith(train_lora.WEIGHT_SUFFIXES) and f.name not in {"config.json", "model.safetensors.index.json"}:
            shutil.copy2(f, merged_dir / f.name)
    del model, merged
    metrics["merge_s"] = round(time.time() - t0, 1)

    llama_cpp = Path(subprocess.run(["bash", str(HERE / "setup_llama_cpp.sh")], check=True,
                                    capture_output=True, text=True).stdout.strip().splitlines()[-1])
    os.environ["PATH"] = f"{llama_cpp / 'bin'}:{os.environ['PATH']}"  # prebuilt llama-quantize
    metrics.update(train_lora.to_gguf(merged_dir, out, tag, llama_cpp, "Q4_K_M", drop_merged=True, outtype="f16"))
    (out / f"{tag}-f16.gguf").unlink(missing_ok=True)  # the laptop only needs the quantized model
    train_lora.write_modelfile(out, metrics["gguf_quant"], os.environ["OLLAMA_RENDERER"], 0.2)
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    if publish_model:
        train_lora.publish(out, f"{models}/{tag}")
    subprocess.run(["ollama", "create", tag, "-f", "Modelfile"], cwd=out, check=True)
    shutil.rmtree(work / "adapter", ignore_errors=True)
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
