"""Pre-compile David's GPU kernels once, so a cold start doesn't.

Ollama's CUDA libraries compile part of their GPU code for the L4 the first time it runs (the CUDA
"JIT"). On a fresh Cloud Run instance that took about 2.5 of the 3.5 minutes of a cold start: model
load 66 s, embedding model 35 s, first translation 62 s (measured 2026-10-07). CUDA keeps what it
compiles in a cache directory; with that cache in place the same three steps took 8 s, 2 s and 1 s.

infra/20-david.sh runs this file as a Cloud Run Job on an L4 with the freshly built image: it starts
Ollama with an empty cache, does everything David does (load both models, retrieval, MBR
translations of short and long phrases in both directions), and uploads the cache to CACHE_URI.
The final image carries that cache (david/Dockerfile.cache). If Cloud Run's GPU driver changes, CUDA
ignores the stale entries and compiles again: slower, never wrong.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tarfile
import time

sys.path[:0] = ["/app", "/app/duel"]

CACHE = os.environ.get("CUDA_CACHE_PATH", "/cuda-cache")
PHRASES = [
    ("Conexión segura", "es-quc"),
    ("Bloquear cookies entre sitios", "es-quc"),
    ("Agregar y gestionar el autocompletado de URL personalizadas.", "es-quc"),
    ("La niña fue al mercado con su abuela para comprar maíz y frijol.", "es-quc"),
    ("Chajital t'iqonem", "quc-es"),
    ("Xinwil jun nim laj che' chuwach ri ja.", "quc-es"),
]


async def main() -> None:
    import httpx

    from tzij_duel.settings import get_settings
    from tzij_duel.variants import david_variant, load_retriever, translate

    os.environ["DAVID_MBR"] = "1"
    s = get_settings()
    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    ollama = subprocess.Popen(["ollama", "serve"], env=dict(os.environ, CUDA_CACHE_PATH=CACHE,
                                                           CUDA_CACHE_MAXSIZE=str(4 << 30)))
    async with httpx.AsyncClient(base_url=s.ollama_url, timeout=600) as http:
        while True:
            try:
                if (await http.get("/api/version")).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.2)
        timings["ollama"] = time.perf_counter() - t0
        variant = david_variant(s)
        t = time.perf_counter()
        await http.post("/api/chat", json={"model": variant.model, "messages": [], "keep_alive": -1,
                                           "options": {"num_ctx": s.ollama_num_ctx}})
        timings["model"] = time.perf_counter() - t
    t = time.perf_counter()
    retriever = load_retriever(s)
    await asyncio.to_thread(retriever.retrieve, "hola", "es-quc", 1)
    timings["embeddings"] = time.perf_counter() - t
    for i, (phrase, direction) in enumerate(PHRASES):
        t = time.perf_counter()
        result = await translate(variant, phrase, direction, retriever=retriever, online=True)
        timings[f"translation_{i}"] = time.perf_counter() - t
        print(f"  {direction} «{phrase}» -> «{result.text}» ({timings[f'translation_{i}']:.1f} s)", flush=True)
    ollama.terminate()
    ollama.wait()
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(CACHE) for f in fs)
    print("WARM", json.dumps({k: round(v, 1) for k, v in timings.items()} | {"cache_mb": round(size / 2**20)}), flush=True)

    with tarfile.open("/tmp/cuda-cache.tgz", "w:gz") as tar:
        tar.add(CACHE, arcname="cuda-cache")
    from google.cloud import storage

    bucket, _, blob = os.environ["CACHE_URI"].removeprefix("gs://").partition("/")
    storage.Client().bucket(bucket).blob(blob).upload_from_filename("/tmp/cuda-cache.tgz")
    print(f"WARM uploaded {os.environ['CACHE_URI']}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
