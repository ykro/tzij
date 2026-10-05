"""`make warmup`: load everything the first round touches, so nothing on stage is cold.

  1. David (LOCAL_MODEL_TAG, with the same num_ctx the rounds use) and the embedding model in Ollama;
  2. one David translation with retrieval (+ MBR when MBR_ON_STAGE=1), exactly as on stage;
  3. one Goliath call (Gemini on Vertex AI).

It runs in its own process with the duel's code (nothing is recorded on the scoreboard).
Exit code 1 if anything failed.

  make warmup
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

import httpx

from duel_core import Connectivity

from .main import _load_retriever
from .settings import get_settings
from .variants import stage_variants, translate

WARMUP_PHRASE = "Buenos días, ¿cómo está usted?"
KEEP_ALIVE = "30m"  # same as `make up` and the duel service


def line(label: str, result: str, ok: bool = True) -> bool:
    print(f"  {label:<44} {result if ok else 'FALLÓ (' + result + ')'}", flush=True)
    return ok


def preload(s) -> bool:
    ok = True
    embedding = os.environ.get("EMBEDDING_MODEL", "")
    loads = [
        (s.david_model, "/api/chat", {"model": s.david_model, "messages": [], "keep_alive": KEEP_ALIVE,
                                      "options": {"num_ctx": s.ollama_num_ctx}}),
        (embedding, "/api/embed", {"model": embedding, "input": ["hola"], "keep_alive": KEEP_ALIVE}),
    ]
    print("Modelos en Ollama", flush=True)
    with httpx.Client(base_url=s.ollama_url, timeout=180) as http:
        for tag, path, body in loads:
            if not tag:
                ok &= line("(sin tag)", "define LOCAL_MODEL_TAG y EMBEDDING_MODEL en .env", ok=False)
                continue
            t0 = time.perf_counter()
            try:
                res = http.post(path, json=body)
                ok &= line(tag, f"cargado en {time.perf_counter() - t0:.1f}s" if res.status_code == 200
                           else f"{res.status_code} {res.text[:80]}", ok=res.status_code == 200)
            except httpx.HTTPError as exc:
                ok &= line(tag, f"{type(exc).__name__}: ¿Ollama corriendo? (make up)", ok=False)
    return ok


async def duel_calls(s) -> bool:
    david, goliath = stage_variants(s)
    retriever = _load_retriever(s)
    online = await Connectivity().is_online()
    mbr = f" + MBR-{david.mbr}" if david.mbr else ""
    print("Una traducción de calentamiento (es → quc, no se registra)", flush=True)
    ok = True
    if retriever is None:
        ok &= line("recuperación", "no hay índice: make index", ok=False)
    d, g = await asyncio.gather(
        translate(david, WARMUP_PHRASE, "es-quc", retriever=retriever, online=online),
        translate(goliath, WARMUP_PHRASE, "es-quc", retriever=None, online=online),
    )
    for label, r in ((f"David ({david.model}, recuperación{mbr})", d), (f"Goliath ({goliath.model})", g)):
        good = r.status == "ok"
        detail = f"{(r.latency_ms or 0) / 1000:.2f}s «{r.text[:40]}»" if good else f"{r.status}: {r.error or ''}"[:120]
        ok &= line(label, detail, ok=good)
    return ok


def main() -> int:
    s = get_settings()
    if s.mock_ai:
        print("MOCK_AI=1: modelos simulados, nada que precalentar. Pon MOCK_AI=0 en .env para la charla.")
        return 1
    ok = preload(s)
    ok &= asyncio.run(duel_calls(s))
    print("warmup ok" if ok else "warmup: algo falló (mira las líneas FALLÓ)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
