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
    # David: the Gemma variant on stage (base or fine-tuned), always with retrieval.
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
    rag_mode: str = field(default_factory=lambda: _env("RAG_MODE", "hybrid"))
    rag_order: str = field(default_factory=lambda: _env("RAG_ORDER", "best_first"))
    rag_fuzzy: bool = field(default_factory=lambda: _env("RAG_FUZZY", "1") == "1")
    # MBR decoding: number of samples (0 = off). Eval variants "+mbrN" use it; on stage only if p50 <= 5 s.
    mbr_samples: int = field(default_factory=lambda: int(_env("MBR_SAMPLES", "0")))
    # Dictionary forms biased per input in the "+bias" llama-server variant (constraints.py).
    max_constraints: int = field(default_factory=lambda: int(_env("MAX_CONSTRAINTS", "3")))
    # llama.cpp llama-server (logit bias + parallel slots); eval variants "@llama" only when set.
    llama_server_url: str = field(default_factory=lambda: _env("LLAMA_SERVER_URL", ""))
    llama_server_model: str = field(default_factory=lambda: _env("LLAMA_SERVER_MODEL", ""))
    llama_mbr_samples: int = field(default_factory=lambda: int(_env("LLAMA_MBR_SAMPLES", "8")))
    llama_temperature: float = field(default_factory=lambda: float(_env("LLAMA_TEMPERATURE", "0.7")))
    llama_min_p: float = field(default_factory=lambda: float(_env("LLAMA_MIN_P", "0.02")))
    llama_bias: float = field(default_factory=lambda: float(_env("LLAMA_BIAS", "2")))
    mock_ai: bool = field(default_factory=lambda: _flag("MOCK_AI"))
    force_offline: bool = field(default_factory=lambda: _flag("FORCE_OFFLINE"))
    state_path: Path = field(default_factory=lambda: REPO_ROOT / _env("DUEL_STATE_PATH", "duel/state/rounds.json"))
    processed_dir: Path = field(default_factory=lambda: REPO_ROOT / "data" / "processed")
    web_dir: Path = field(default_factory=lambda: REPO_ROOT / "web" / "out")
    port: int = field(default_factory=lambda: int(_env("DUEL_PORT", "8787")))
    # URL the phone opens (QR). Empty: detected from the laptop's LAN address.
    public_url: str = field(default_factory=lambda: _env("PUBLIC_URL"))
    # On stage, evaluation rounds should use references a native speaker validated.
    require_validated_test: bool = field(default_factory=lambda: _flag("REQUIRE_VALIDATED_TEST"))


def get_settings() -> Settings:
    return Settings()
