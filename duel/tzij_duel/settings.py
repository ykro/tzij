"""All configuration comes from env vars (see `.env.example`). No model names in code."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _flag(name: str) -> bool:
    return _env(name, "0").lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    raw = _env(name)
    return float(raw) if raw else default


def _list(name: str) -> list[str]:
    return [x.strip() for x in _env(name).split(",") if x.strip()]


@dataclass
class Settings:
    project: str = field(default_factory=lambda: _env("GOOGLE_CLOUD_PROJECT", "ai-experiments-487722"))
    location: str = field(default_factory=lambda: _env("GOOGLE_CLOUD_LOCATION", "global"))
    gemini_model: str = field(default_factory=lambda: _env("GEMINI_MODEL"))
    gemini_thinking_level: str = field(default_factory=lambda: _env("GEMINI_THINKING_LEVEL", "low"))
    gemini_input_usd_per_m: float = field(default_factory=lambda: _float("GEMINI_INPUT_USD_PER_M", 0.0))
    gemini_output_usd_per_m: float = field(default_factory=lambda: _float("GEMINI_OUTPUT_USD_PER_M", 0.0))
    # "YYYY-MM-DD:input/output": Gemini's announced list price from that day on (the page uses the
    # price of the day of each translation).
    gemini_next_price: str = field(default_factory=lambda: _env("GEMINI_NEXT_PRICE"))
    # David: the Gemma variant the page shows (fine-tuned), always with retrieval.
    david_model: str = field(default_factory=lambda: _env("LOCAL_MODEL_TAG"))
    # Extra Ollama models compared in `make eval` (base E2B vs E4B, fine-tuned tags later).
    base_model_tags: list[str] = field(default_factory=lambda: _list("BASE_MODEL_TAGS"))
    finetuned_model_tags: list[str] = field(default_factory=lambda: _list("FINETUNED_MODEL_TAGS"))
    ollama_url: str = field(default_factory=lambda: _env("OLLAMA_URL") or _env("OLLAMA_HOST", "http://127.0.0.1:11434"))
    # A 128k default context makes Ollama reserve a huge KV cache: slower, and it evicts the
    # embedding model on every request. Translations need a few hundred tokens.
    ollama_num_ctx: int = field(default_factory=lambda: int(_env("OLLAMA_NUM_CTX", "4096")))
    rag_index: Path = field(default_factory=lambda: REPO_ROOT / _env("RAG_INDEX", "rag/index/tzij.sqlite"))
    rag_k: int = field(default_factory=lambda: int(_env("RAG_K", "6")))
    # Retrieval for David (and the "+hybrid" eval variants): tuned on the dev split (evals/tuning.md).
    # The defaults match .env.example, which David's image carries as its .env.
    rag_mode: str = field(default_factory=lambda: _env("RAG_MODE", "hybrid"))
    rag_order: str = field(default_factory=lambda: _env("RAG_ORDER", "best_last"))
    rag_fuzzy: bool = field(default_factory=lambda: _env("RAG_FUZZY", "1") == "1")
    # Extra retrieval options, off until dev says otherwise: trigram list (RRF) and n-gram coverage selection.
    rag_trigram: bool = field(default_factory=lambda: _env("RAG_TRIGRAM", "0") == "1")
    rag_select: str = field(default_factory=lambda: _env("RAG_SELECT", "rank"))
    # MBR decoding: number of samples (0 = off). Eval variants "+mbrN" use it; David's service when DAVID_MBR=1.
    mbr_samples: int = field(default_factory=lambda: int(_env("MBR_SAMPLES", "0")))
    mock_ai: bool = field(default_factory=lambda: _flag("MOCK_AI"))
    # The page's backend calls David's GPU service here (Cloud Run, private). Empty: David runs in
    # the same process (tests, MOCK_AI=1).
    david_url: str = field(default_factory=lambda: _env("DAVID_URL"))
    # What David's GPU instance costs per second while it's up (Cloud Run instance-based billing:
    # L4 + vCPU + memory, europe-west4). The page multiplies it by the seconds David worked.
    david_gpu_usd_per_s: float = field(default_factory=lambda: _float("DAVID_GPU_USD_PER_S", 0.0001867))
    david_vcpu_usd_per_s: float = field(default_factory=lambda: _float("DAVID_VCPU_USD_PER_S", 0.000018))
    david_gib_usd_per_s: float = field(default_factory=lambda: _float("DAVID_GIB_USD_PER_S", 0.000002))
    david_cpu: int = field(default_factory=lambda: int(_env("DAVID_CPU", "4")))
    david_memory_gib: int = field(default_factory=lambda: int(_env("DAVID_MEMORY_GIB", "16")))
    processed_dir: Path = field(default_factory=lambda: REPO_ROOT / "data" / "processed")
    web_dir: Path = field(default_factory=lambda: REPO_ROOT / "web" / "out")


def david_usd_per_s(s: Settings) -> float:
    """David's GPU instance, per second while it's up: L4 + vCPUs + GiB of memory."""
    return s.david_gpu_usd_per_s + s.david_cpu * s.david_vcpu_usd_per_s + s.david_memory_gib * s.david_gib_usd_per_s


def gemini_price_on(s: Settings, day) -> tuple[float, float]:
    """Gemini's list price (input, output USD per 1M tokens) on that day."""
    if s.gemini_next_price:
        start, _, prices = s.gemini_next_price.partition(":")
        if day.isoformat() >= start.strip():
            inp, _, out = prices.partition("/")
            return float(inp), float(out)
    return s.gemini_input_usd_per_m, s.gemini_output_usd_per_m


def get_settings() -> Settings:
    return Settings()
