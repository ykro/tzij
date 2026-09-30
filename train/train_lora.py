"""Fine-tune a small Gemma with LoRA, merge, quantize to GGUF and publish it for Ollama.

End to end, one command (runs inside the Vertex AI Custom Job, in Colab, or locally):

    python train_lora.py --data gs://…/train.jsonl --tag genlingo-2027-03 \
        --base-model gemma-4-E2B-it --weights-uri gs://vertex-model-garden-public-us/gemma4 \
        --output-uri gs://ai-experiments-487722-genlingo-models

Stages (each timed in metrics.json):
  1. weights   download the base checkpoint (Model Garden public bucket: no Hugging Face token)
  2. train     LoRA with TRL + PEFT: only ~0.5% of the weights learn; the rest stay frozen
  3. merge     fold the adapter back into the base weights -> a normal checkpoint
  4. gguf      llama.cpp: convert to GGUF f16, then quantize to Q4_K_M (~4x smaller)
  5. publish   Modelfile + GGUFs + adapter + metrics to gs://<bucket>/<tag>/

The data file is chat-formatted JSONL: {"messages": [system, user, assistant]}. The app renders
it with the same prompt the duel uses, so this script knows nothing about slang: it only
learns "given these messages, answer like the assistant turn".
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

WEIGHT_SUFFIXES = (".safetensors", ".bin", ".pt")


def log(msg: str) -> None:
    print(f"[train_lora {time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------------------------
# I/O helpers: gs:// or local paths, so the same script runs in the cloud and on a laptop
# ---------------------------------------------------------------------------------------------
def _gcs():
    from google.cloud import storage

    return storage.Client()


def _split_gs(uri: str) -> tuple[str, str]:
    bucket, _, prefix = uri.removeprefix("gs://").partition("/")
    return bucket, prefix.strip("/")


def fetch(uri: str, dest: Path) -> Path:
    """Copy a file or a gs:// prefix to `dest` (a file path or a directory)."""
    if not uri.startswith("gs://"):
        return Path(uri)
    from google.cloud.storage import transfer_manager

    bucket_name, prefix = _split_gs(uri)
    bucket = _gcs().bucket(bucket_name)
    single = bucket.blob(prefix)
    if single.exists():  # a single file
        dest.parent.mkdir(parents=True, exist_ok=True)
        single.download_to_filename(dest)
        return dest
    # A "directory": list with a trailing slash so gemma-4-E2B-it doesn't also match gemma-4-E2B-it-assistant.
    blobs = [b for b in bucket.list_blobs(prefix=prefix + "/") if not b.name.endswith("/")]
    dest.mkdir(parents=True, exist_ok=True)
    for b in blobs:
        target = dest / Path(b.name).relative_to(prefix)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.stat().st_size == b.size:
            continue
        if b.size and b.size > 256 * 1024**2:  # big shards: parallel ranged download
            transfer_manager.download_chunks_concurrently(b, str(target), chunk_size=64 * 1024**2, max_workers=16)
        else:
            b.download_to_filename(target)
    return dest


def publish(local_dir: Path, uri: str, only: list[str] | None = None) -> None:
    if not uri.startswith("gs://"):
        shutil.copytree(local_dir, uri, dirs_exist_ok=True)
        return
    bucket_name, prefix = _split_gs(uri)
    bucket = _gcs().bucket(bucket_name)
    for f in sorted(local_dir.iterdir()):
        if f.is_file() and (only is None or f.name in only):
            log(f"upload {f.name} ({f.stat().st_size / 1e9:.2f} GB)")
            blob = bucket.blob(f"{prefix}/{f.name}")
            if f.stat().st_size > 256 * 1024**2:
                from google.cloud.storage import transfer_manager

                try:  # parallel parts: fast inside GCP
                    transfer_manager.upload_chunks_concurrently(
                        str(f), blob, chunk_size=64 * 1024**2, max_workers=8, worker_type=transfer_manager.THREAD
                    )
                    continue
                except Exception as exc:  # slow home uplinks time out: fall back to one resumable upload
                    log(f"parallel upload failed ({type(exc).__name__}), retrying as a single resumable upload")
            blob.chunk_size = 64 * 1024**2
            blob.upload_from_filename(f, timeout=3600)


def hf_token_from_secret_manager(project: str | None, secret: str = "hf-token") -> str | None:
    """Read from Secret Manager so the token never lives in the image, the job spec or the repo.
    Missing secret or no access -> None (anonymous download)."""
    if not project:
        return None
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    url = f"https://secretmanager.googleapis.com/v1/projects/{project}/secrets/{secret}/versions/latest:access"
    try:
        res = AuthorizedSession(creds).get(url, timeout=10)
    except Exception as exc:  # no network to Secret Manager: go anonymous
        log(f"secret {secret} not reachable ({type(exc).__name__})")
        return None
    if res.status_code != 200:
        log(f"secret {secret} not readable ({res.status_code})")
        return None
    import base64

    return base64.b64decode(res.json()["payload"]["data"]).decode().strip()


def base_weights(base_model: str, weights_uri: str, work: Path) -> Path:
    """Model Garden (gs://…/<name>) by default; Hugging Face (hf://org) only if asked, with HF_TOKEN."""
    if weights_uri.startswith("hf://"):
        from huggingface_hub import snapshot_download

        repo = f"{weights_uri.removeprefix('hf://').strip('/')}/{base_model}"
        return Path(snapshot_download(repo, local_dir=work / base_model, token=os.environ.get("HF_TOKEN") or None))
    if weights_uri.startswith("gs://"):
        return fetch(f"{weights_uri.rstrip('/')}/{base_model}", work / base_model)
    return Path(weights_uri) / base_model


# ---------------------------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------------------------
def load_dataset(path: Path, tokenizer):
    """Chat rows -> prompt/completion text. TRL then computes the loss on the completion only:
    we teach the model to answer, not to repeat our system prompt."""
    from datasets import Dataset

    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        msgs = json.loads(line)["messages"]
        prompt_msgs, answer = msgs[:-1], msgs[-1]
        assert answer["role"] == "assistant", "last message must be the assistant answer"
        full = tokenizer.apply_chat_template(msgs, tokenize=False)
        prompt = tokenizer.apply_chat_template(prompt_msgs, tokenize=False, add_generation_prompt=True)
        assert full.startswith(prompt), "chat template must render the prompt as a prefix of the full chat"
        bos = tokenizer.bos_token or ""
        # The template adds <bos> itself and TRL tokenizes with special tokens: drop it to avoid
        # a double <bos>. TRL appends <eos> to the completion, so trailing whitespace goes too.
        rows.append({"prompt": prompt.removeprefix(bos), "completion": full[len(prompt):].rstrip()})
    return Dataset.from_list(rows)


# ---------------------------------------------------------------------------------------------
# Train + merge
# ---------------------------------------------------------------------------------------------
def train_and_merge(args, base_dir: Path, data_path: Path, work: Path) -> dict:
    import torch
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    dtype = torch.bfloat16 if device != "cpu" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(base_dir)
    dataset = load_dataset(data_path, tokenizer)
    log(f"{len(dataset)} training examples, device={device}")

    model = AutoModelForCausalLM.from_pretrained(base_dir, dtype=dtype, attn_implementation="eager")

    lora = LoraConfig(
        r=args.lora_r,  # rank of the update matrices: capacity of what the adapter can learn
        lora_alpha=args.lora_alpha,  # scale of the update (alpha/r = 2 is a common, stable choice)
        lora_dropout=0.05,
        # Only the text decoder learns. Gemma 4 small models also carry vision/audio towers;
        # translating slang doesn't need them, so they stay frozen and untouched.
        target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)",
        task_type="CAUSAL_LM",
    )
    cfg = SFTConfig(
        output_dir=str(work / "checkpoints"),
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,  # -1 = use epochs; small numbers for smoke tests
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=0.03,  # float < 1 = ratio of total steps
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        gradient_checkpointing=device == "cuda",
        bf16=device != "cpu",
        max_length=args.max_length,
        completion_only_loss=True,
        logging_steps=5,
        save_strategy="no",
        report_to="none",
        seed=args.seed,
    )
    trainer = SFTTrainer(model=model, args=cfg, train_dataset=dataset, processing_class=tokenizer, peft_config=lora)
    trainable, total = trainer.model.get_nb_trainable_parameters()
    log(f"trainable params: {trainable / 1e6:.1f}M of {total / 1e9:.2f}B ({100 * trainable / total:.2f}%)")
    t0 = time.time()
    result = trainer.train()
    train_s = time.time() - t0
    losses = [h["loss"] for h in trainer.state.log_history if "loss" in h]

    adapter_dir = work / "adapter"
    trainer.model.save_pretrained(adapter_dir)

    # Merge: W' = W + (alpha/r)·B·A. After this there is no adapter at inference time,
    # so llama.cpp/Ollama see an ordinary model.
    t1 = time.time()
    merged = trainer.model.merge_and_unload()
    merged_dir = work / "merged"
    merged.save_pretrained(merged_dir, safe_serialization=True)
    for f in base_dir.iterdir():  # tokenizer, chat template, processor config… (not weights/config)
        if f.is_file() and not f.name.endswith(WEIGHT_SUFFIXES) and f.name not in {"config.json", "model.safetensors.index.json"}:
            shutil.copy2(f, merged_dir / f.name)
    merge_s = time.time() - t1
    return {
        "examples": len(dataset),
        "trainable_params": trainable,
        "total_params": total,
        "train_loss_first": losses[0] if losses else None,
        "train_loss_last": losses[-1] if losses else None,
        "train_loss_mean": result.training_loss,
        "steps": trainer.state.global_step,
        "device": device,
        "train_s": round(train_s, 1),
        "merge_s": round(merge_s, 1),
        "merged_dir": str(merged_dir),
        "adapter_dir": str(adapter_dir),
    }


# ---------------------------------------------------------------------------------------------
# GGUF + Modelfile
# ---------------------------------------------------------------------------------------------
def to_gguf(merged_dir: Path, out_dir: Path, tag: str, llama_cpp: Path, quant: str) -> dict:
    """f16 GGUF (the "uncompressed" reference) and a quantized one (what the laptop runs).
    Q4_K_M keeps ~4.5 bits per weight with mixed precision on the most sensitive tensors."""
    out_dir.mkdir(parents=True, exist_ok=True)
    f16 = out_dir / f"{tag}-f16.gguf"
    q = out_dir / f"{tag}-{quant.lower()}.gguf"
    t0 = time.time()
    subprocess.run(
        [sys.executable, str(llama_cpp / "convert_hf_to_gguf.py"), str(merged_dir), "--outtype", "f16", "--outfile", str(f16)],
        check=True,
    )
    quantize = shutil.which("llama-quantize") or str(llama_cpp / "llama-quantize")
    subprocess.run([quantize, str(f16), str(q), quant], check=True)
    return {"gguf_f16": f16.name, "gguf_quant": q.name, "quant": quant, "f16_bytes": f16.stat().st_size,
            "quant_bytes": q.stat().st_size, "gguf_s": round(time.time() - t0, 1)}


def write_modelfile(out_dir: Path, gguf_name: str, renderer: str, temperature: float) -> Path:
    """Ollama recipe. RENDERER/PARSER reuse Ollama's built-in chat format for the model family,
    so the fine-tuned model is prompted exactly like the base model it came from."""
    lines = [f"FROM ./{gguf_name}"]
    if renderer:
        lines += [f"RENDERER {renderer}", f"PARSER {renderer}"]
    lines += [f"PARAMETER temperature {temperature}", "PARAMETER top_p 0.95", "PARAMETER num_ctx 2048"]
    path = out_dir / ("Modelfile" if "f16" not in gguf_name else "Modelfile.f16")
    path.write_text("\n".join(lines) + "\n")
    return path


# ---------------------------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    env = os.environ.get
    ap = argparse.ArgumentParser(description="LoRA fine-tune -> merge -> GGUF -> Ollama Modelfile -> GCS")
    ap.add_argument("--data", required=True, help="chat JSONL (local path or gs://)")
    ap.add_argument("--tag", required=True, help="model tag with the data date, e.g. genlingo-2027-03")
    ap.add_argument("--base-model", default=env("GEMMA_BASE_MODEL"))
    ap.add_argument("--weights-uri", default=env("GEMMA_WEIGHTS_URI", "gs://vertex-model-garden-public-us/gemma4"))
    ap.add_argument("--output-uri", default=env("MODELS_BUCKET"), help="gs://bucket (the tag is appended); empty = keep local")
    ap.add_argument("--work-dir", default=env("WORK_DIR", "/tmp/train_lora"))
    ap.add_argument("--llama-cpp", default=env("LLAMA_CPP_DIR", "/opt/llama.cpp"))
    ap.add_argument("--quant", default="Q4_K_M")
    ap.add_argument("--ollama-renderer", default=env("OLLAMA_RENDERER", "gemma4"))
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--max-steps", type=int, default=-1)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--grad-accum", type=int, default=2)
    ap.add_argument("--max-length", type=int, default=256)
    ap.add_argument("--seed", type=int, default=2027)
    ap.add_argument("--skip-gguf", action="store_true", help="stop after merge (no llama.cpp available)")
    args = ap.parse_args(argv)
    if not args.base_model:
        ap.error("--base-model or GEMMA_BASE_MODEL is required")
    return args


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    work = Path(args.work_dir)
    out = work / "out"
    out.mkdir(parents=True, exist_ok=True)
    metrics: dict = {"tag": args.tag, "base_model": args.base_model, "weights_uri": args.weights_uri,
                     "hyperparams": {k: getattr(args, k) for k in ("lora_r", "lora_alpha", "lr", "epochs", "batch_size", "grad_accum", "max_length", "seed")}}
    t_all = time.time()

    # Hugging Face token: from the env, else from Secret Manager (`hf-token`) when it exists,
    # else anonymous. Gemma 4 isn't gated, but anonymous downloads from cloud IPs can get 429s.
    if not os.environ.get("HF_TOKEN"):
        token = hf_token_from_secret_manager(os.environ.get("GOOGLE_CLOUD_PROJECT"))
        if token:
            os.environ["HF_TOKEN"] = token
    log(f"Hugging Face token: {'yes' if os.environ.get('HF_TOKEN') else 'no (anonymous)'}")

    t0 = time.time()
    base_dir = base_weights(args.base_model, args.weights_uri, work / "base")
    data_path = fetch(args.data, work / "train.jsonl")
    metrics["weights_s"] = round(time.time() - t0, 1)
    log(f"base weights at {base_dir} ({metrics['weights_s']}s)")

    metrics.update(train_and_merge(args, base_dir, data_path, work))
    shutil.make_archive(str(out / f"{args.tag}-adapter"), "zip", metrics.pop("adapter_dir"))

    if not args.skip_gguf:
        metrics.update(to_gguf(Path(metrics["merged_dir"]), out, args.tag, Path(args.llama_cpp), args.quant))
        write_modelfile(out, metrics["gguf_quant"], args.ollama_renderer, args.temperature)
        write_modelfile(out, metrics["gguf_f16"], args.ollama_renderer, args.temperature)

    metrics["total_s"] = round(time.time() - t_all, 1)
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    if args.output_uri:
        t0 = time.time()
        publish(out, f"{args.output_uri.rstrip('/')}/{args.tag}")
        metrics["publish_s"] = round(time.time() - t0, 1)
        (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
        publish(out, f"{args.output_uri.rstrip('/')}/{args.tag}", only=["metrics.json"])
    log(json.dumps(metrics))
    return metrics


if __name__ == "__main__":
    main()
