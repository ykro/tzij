"""David's service: the fine-tuned Gemma, its retrieval index and MBR decoding, on a Cloud Run L4 GPU.

Runs in the same container as Ollama (david/Dockerfile). Private: only the page's service account
(and the project's owners, for evals) can call it.

  GET  /health      {"ready": bool}: true once the model, the embedding model and the index are loaded
  POST /translate   {"text", "direction"} -> David's translation (retrieval + MBR-4), timed here
  POST /reference   {"text", "direction"} -> the licensed correct translation of exactly that phrase, if any
  POST /evidence    {"text", "direction", "outputs"} -> what helps judge a typed phrase (evidence.py)
  *    /api/...     Ollama's API, for `make eval` / `make tune-retrieval` through `make david-proxy`
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from rag.retrieve import Retriever

from .evidence import Evidence
from .settings import REPO_ROOT, Settings, get_settings
from .variants import Variant, david_variant, load_retriever, translate

MAX_PHRASE_CHARS = 280
MOCK_DATA = REPO_ROOT / "duel" / "mock_data"
# Licensed test pairs (test + test_niche, never BOUQuET), copied next to the index by david/cloudbuild.yaml.
REFERENCES = REPO_ROOT / "rag" / "index" / "references.jsonl"


class Translation(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_PHRASE_CHARS)
    direction: Literal["es-quc", "quc-es"] = "es-quc"


class EvidenceRequest(Translation):
    outputs: dict[str, str] = Field(default_factory=dict)


def mock_retriever(settings: Settings) -> Retriever:
    """MOCK_AI=1 (tests): a tiny index of licensed pairs with hashing embeddings, no Ollama."""
    import json
    import tempfile
    from pathlib import Path

    from rag.build_index import build
    from rag.embedder import HashingEmbedder

    records = [json.loads(line) for line in (MOCK_DATA / "index_pairs.jsonl").read_text(encoding="utf-8").splitlines()]
    path = Path(tempfile.mkdtemp()) / "mock-index.sqlite"
    build(records, HashingEmbedder(), path, "mock")
    return Retriever(path, embedder=HashingEmbedder())


class David:
    def __init__(self, settings: Settings, variant: Variant | None = None, retriever: Retriever | None = None) -> None:
        self.settings = settings
        self.variant = variant or david_variant(settings)
        self.retriever = retriever if retriever is not None else (
            mock_retriever(settings) if settings.mock_ai else load_retriever(settings))
        self.evidence = Evidence(self.retriever, REFERENCES)
        self.ready = settings.mock_ai
        self._warm = asyncio.Event()
        if self.ready:
            self._warm.set()

    async def wait_ready(self, timeout_s: float = 280.0) -> None:
        """A translation that arrives while David is still loading waits for the one warm-up."""
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._warm.wait(), timeout_s)

    async def warm_up(self) -> None:
        """Load the model into the GPU with the context size translations use, and the embedding model:
        the first translation after a cold start then takes the same time as the rest."""
        if self.settings.mock_ai:
            return
        try:
            await self._load()
        finally:
            self._warm.set()  # ready or not, waiting translations go ahead (and report their own error)

    async def _load(self) -> None:
        async with httpx.AsyncClient(base_url=self.settings.ollama_url, timeout=300) as http:
            for _ in range(120):  # ollama serve starts with the container; wait for it
                with contextlib.suppress(httpx.HTTPError):
                    if (await http.get("/api/version")).status_code == 200:
                        break
                await asyncio.sleep(0.5)
            await http.post("/api/chat", json={"model": self.variant.model, "messages": [], "keep_alive": -1,
                                               "options": {"num_ctx": self.settings.ollama_num_ctx}})
        if self.retriever is not None:
            await asyncio.to_thread(self.retriever.retrieve, "hola", "es-quc", 1)
        result = await translate(self.variant, "Conexión segura", "es-quc", retriever=self.retriever, online=True)
        self.ready = result.status == "ok"
        print(f"David listo: {self.ready} ({result.latency_ms} ms, «{result.text}»)", flush=True)

    async def translate(self, body: Translation) -> dict[str, Any]:
        text = body.text.strip()
        if not text:
            raise HTTPException(422, "Escribe una frase para traducir.")
        r = await translate(self.variant, text, body.direction, retriever=self.retriever, online=True)
        return {"status": r.status, "text": r.text, "latency_ms": r.latency_ms, "error": r.error,
                "model": r.model, "input_tokens": r.input_tokens, "output_tokens": r.output_tokens}


def create_app(settings: Settings | None = None, david: David | None = None) -> FastAPI:
    settings = settings or get_settings()
    svc = david or David(settings)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        # Warm up in the background: the port opens right away (Cloud Run's startup check), and
        # /health says ready only once David can translate at full speed.
        task = asyncio.create_task(svc.warm_up())
        yield
        task.cancel()

    app = FastAPI(title="Tzij · David", lifespan=lifespan)
    app.state.david = svc

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ready": svc.ready, "model": svc.variant.model, "retrieval": svc.retriever is not None}

    @app.post("/translate")
    async def translate_text(body: Translation) -> dict[str, Any]:
        await svc.wait_ready()
        return await svc.translate(body)

    @app.post("/reference")
    async def reference(body: Translation) -> dict[str, Any]:
        return {"reference": svc.evidence.reference(body.text, body.direction)}

    @app.post("/evidence")
    async def evidence(body: EvidenceRequest) -> dict[str, Any]:
        await svc.wait_ready()
        return await asyncio.to_thread(svc.evidence.evidence, body.text, body.direction,
                                       {k: v[:MAX_PHRASE_CHARS * 2] for k, v in body.outputs.items()})

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "DELETE"], include_in_schema=False)
    async def ollama_api(path: str, request: Request) -> Response:
        """Ollama's own API, so the evals can run against the cloud David (`make david-proxy`)."""
        async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=600) as http:
            res = await http.request(request.method, f"/api/{path}", content=await request.body(),
                                     headers={"content-type": request.headers.get("content-type", "application/json")})
        return Response(res.content, status_code=res.status_code, media_type=res.headers.get("content-type"))

    return app
