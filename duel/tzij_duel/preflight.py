"""Talk-day gate: everything the live demo needs, checked in one go (all on the laptop).

  make preflight        (after `make warmup`; with `make up` running, its /api/health is checked too)

One Spanish line per check, `[ok]` or `[FALLA]` with the fix. Exit code = number of failures.
  - Ollama up, David (LOCAL_MODEL_TAG) and the embedding model present
  - David never trained on Firefox Focus (otherwise the specialty round is not a fair test)
  - the retrieval index exists, loads, and comes from the dataset in data/processed/LATEST
  - the evaluation deck and the specialty deck (test_niche) have phrases
  - the duel service's /api/health, if it is running
  - Gemini answers (one tiny call)
  - at least 10 GB free on disk
  - one timed David translation as on stage (retrieval + MBR if MBR_ON_STAGE=1) within the 5 s p50 budget
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys

import httpx

from duel_core import GeminiClient

from .deck import Deck, latest_dataset
from .main import _load_retriever, index_mismatch
from .settings import REPO_ROOT, get_settings
from .variants import stage_variants, translate

MIN_FREE_GB = 10
P50_BUDGET_S = 5.0  # the stage budget David's variant was chosen under (evals/report.md)
TIMED_PHRASE = "¿Dónde está el mercado del pueblo?"
# Fine-tunes whose training data included Firefox Focus (trained before the niche was held out on
# 2 Oct; docs/BITACORA.md section 6). With them the specialty round would test memorization.
FOCUS_TRAINED = {
    "tzij-2026-09",
    "tzij-2026-10-raft-s0",
    "tzij-2026-10-raft-bt-s0",
    "tzij-2026-10-raft-bt-s1",
    "tzij-2026-10-raft-bt-s2",
    "tzij-2026-10-raft-bt-s3",
}


class Report:
    def __init__(self) -> None:
        self.failures = 0

    def ok(self, text: str) -> None:
        print(f"  [ok]    {text}", flush=True)

    def fail(self, text: str, fix: str) -> None:
        self.failures += 1
        print(f"  [FALLA] {text}\n          → {fix}", flush=True)


def check_ollama(r: Report, s) -> None:
    print("Ollama", flush=True)
    embedding = os.environ.get("EMBEDDING_MODEL", "")
    try:
        models = httpx.get(s.ollama_url + "/api/tags", timeout=5).json().get("models", [])
    except httpx.HTTPError as exc:
        r.fail(f"Ollama no responde en {s.ollama_url} ({type(exc).__name__})", "make up (arranca Ollama)")
        return
    names = {(m.get("name") or "").removesuffix(":latest") for m in models}
    r.ok(f"Ollama responde ({len(names)} modelos)")
    for tag, role, fix in [(s.david_model, "David", f"make pull-model TAG={s.david_model}"),
                           (embedding, "embeddings", f"ollama pull {embedding}")]:
        if not tag:
            r.fail(f"{role}: sin tag en .env", "define LOCAL_MODEL_TAG y EMBEDDING_MODEL en .env")
        elif tag.removesuffix(":latest") in names:
            r.ok(f"{role}: {tag}")
        else:
            r.fail(f"{role}: {tag} no está en Ollama", fix)
    tag = s.david_model.removesuffix(":latest")
    if tag in FOCUS_TRAINED:
        r.fail(f"{tag} entrenó con Firefox Focus: ya vio las frases de la ronda de especialidad (S) y la ronda no sería justa",
               "LOCAL_MODEL_TAG=tzij-2026-10-mix-s7 (o la base gemma4:e4b) en .env, y reinicia make up")
    else:
        r.ok(f"{tag} no entrenó con Firefox Focus (la ronda de especialidad vale)")


def check_index_and_decks(r: Report, s):
    print("Índice de recuperación y frases", flush=True)
    dataset = latest_dataset(s.processed_dir)
    if dataset is None:
        r.fail("No hay dataset en data/processed/LATEST", "make data-pull && make niche-data")
    retriever = _load_retriever(s)
    if retriever is None:
        r.fail(f"El índice {s.rag_index.relative_to(REPO_ROOT)} no existe o no carga", "make index")
    elif (warning := index_mismatch(retriever, s.processed_dir)):
        r.fail(warning, "make index")
    else:
        r.ok(f"Índice del dataset {retriever.dataset_version} (igual que LATEST), modo {s.rag_mode}")
    deck = Deck(s.processed_dir, require_validated=s.require_validated_test)
    general = len(deck.items) - deck.niche_size
    if general:
        r.ok(f"Rondas de evaluación (E): {general} frases")
    else:
        r.fail("No hay frases para las rondas de evaluación", "make data-pull && make niche-data (o revisa REQUIRE_VALIDATED_TEST)")
    niche_file = dataset / "test_niche.jsonl" if dataset else None
    if deck.niche_size and niche_file and niche_file.exists():
        r.ok(f"Ronda de especialidad (S, Firefox Focus): {deck.niche_size} frases en {niche_file.name}")
    else:
        r.fail("Falta el mazo de especialidad (test_niche.jsonl) o está vacío", "make niche-data")
    return retriever


def check_duel(r: Report, s) -> None:
    print("Servicio del duelo", flush=True)
    try:
        h = httpx.get(f"http://127.0.0.1:{s.port}/api/health", timeout=3).json()
    except (httpx.HTTPError, ValueError):
        r.ok(f"No está corriendo en :{s.port}; se revisa cuando corras make up (no es una falla)")
        return
    if h.get("mock"):
        r.fail("El duelo corre con MOCK_AI=1", "pon MOCK_AI=0 en .env y reinicia make up")
    elif not h.get("retrieval"):
        r.fail("El duelo corre sin recuperación", "make index y reinicia make up")
    elif not h.get("online"):
        r.fail("El duelo no ve internet: Goliath saldría «Sin conexión»", "revisa el Wi-Fi o FORCE_OFFLINE en .env")
    else:
        r.ok(f"/api/health en :{s.port}: en línea, con recuperación")


def check_gemini(r: Report, s) -> None:
    print("Goliath (Gemini en Vertex AI)", flush=True)
    if not s.gemini_model:
        r.fail("GEMINI_MODEL vacío", "define GEMINI_MODEL en .env")
        return
    try:
        client = GeminiClient(s.project, s.location, thinking_level=s.gemini_thinking_level or None)
        res = asyncio.run(client.complete([{"role": "user", "content": "Responde solo: ok"}], model=s.gemini_model))
        r.ok(f"{s.gemini_model} responde en {res.latency_ms / 1000:.2f}s ({res.input_tokens}+{res.output_tokens} tokens)")
    except Exception as exc:
        r.fail(f"{s.gemini_model} no responde ({type(exc).__name__}: {str(exc)[:100]})",
               "gcloud auth application-default login y revisa la conexión")


def check_disk(r: Report) -> None:
    print("Disco", flush=True)
    free_gb = shutil.disk_usage(REPO_ROOT).free / 1e9
    if free_gb >= MIN_FREE_GB:
        r.ok(f"Disco libre: {free_gb:.0f} GB")
    else:
        r.fail(f"Disco libre: {free_gb:.1f} GB (mínimo {MIN_FREE_GB} GB)", "borra modelos que no salen en escena (ollama rm <tag>)")


def check_david_latency(r: Report, s, retriever) -> None:
    david, _ = stage_variants(s)
    mbr = f" + MBR-{david.mbr}" if david.mbr else ""
    print(f"Latencia de David (recuperación{mbr}, como en escena)", flush=True)
    if retriever is None:
        r.fail("Sin índice no se puede medir a David como en escena", "make index")
        return
    res = asyncio.run(translate(david, TIMED_PHRASE, "es-quc", retriever=retriever, online=False))
    if res.status != "ok":
        r.fail(f"David falló: {res.status} {res.error or ''}"[:140], "make warmup y revisa Ollama")
        return
    seconds = (res.latency_ms or 0) / 1000
    if seconds <= P50_BUDGET_S:
        r.ok(f"{seconds:.2f}s (presupuesto p50: {P50_BUDGET_S:.0f} s) «{res.text[:40]}»")
    else:
        fix = "make warmup (¿modelo frío?); si sigue lento, MBR_ON_STAGE=0 en .env" if david.mbr else "make warmup (¿modelo frío?) y cierra apps pesadas"
        r.fail(f"{seconds:.2f}s, más que el presupuesto p50 de {P50_BUDGET_S:.0f} s", fix)


def main() -> int:
    s = get_settings()
    r = Report()
    if s.mock_ai:
        r.fail("MOCK_AI=1: en escena los modelos serían simulados", "pon MOCK_AI=0 en .env")
    check_ollama(r, s)
    retriever = check_index_and_decks(r, s)
    check_duel(r, s)
    check_gemini(r, s)
    check_disk(r)
    if not s.mock_ai:
        check_david_latency(r, s, retriever)
    print()
    if r.failures:
        print(f"preflight FALLÓ: {r.failures} problema(s). Corrígelos antes de subir al escenario.")
    else:
        print("preflight ok: listo para la charla.")
    return r.failures


if __name__ == "__main__":
    sys.exit(main())
