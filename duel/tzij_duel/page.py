"""The demo page's service (public Cloud Run): David and Goliath translate the same text side by side.

  /               the page (static export of web/)
  /api/examples   the example phrases, each with its licensed correct translation
  /api/info       model names for the two columns
  /api/david      {"ready": bool}: also wakes David's GPU service when it was asleep
  /api/translate  one side's translation; the page asks for each side on its own so each column
                  fills as soon as its model answers

David runs on his own GPU service (david_app.py, private); Goliath is Gemini on Vertex AI, called
from here. Both times are measured here, as the person in front of the page waits them.
"""

from __future__ import annotations

import time
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from duel_core import chrf_pp

from .david_app import David
from .david_app import Translation as DavidRequest
from .examples import load_examples, public
from .remote import DavidUnavailable, RemoteDavid
from .settings import Settings, get_settings
from .variants import Variant, goliath_variant, translate

MAX_PHRASE_CHARS = 280
Side = Literal["david", "goliath"]


class Translation(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_PHRASE_CHARS)
    direction: Literal["es-quc", "quc-es"] = "es-quc"
    # An example button sends its pair_id: the page then shows the licensed correct translation
    # and how close each side got to it. Typed text has no reference.
    example: str | None = None
    side: Side | None = None


class InProcessDavid:
    """Tests and MOCK_AI=1: David runs in this process instead of on the GPU service."""

    def __init__(self, settings: Settings) -> None:
        self.david = David(settings)

    async def health(self, timeout_s: float = 4.0) -> bool:
        return True

    async def translate(self, text: str, direction: str) -> dict[str, Any]:
        return await self.david.translate(DavidRequest(text=text, direction=direction))


class Page:
    def __init__(self, settings: Settings, *, david: Any = None, goliath: Variant | None = None) -> None:
        self.settings = settings
        self.david = david or (RemoteDavid(settings.david_url) if settings.david_url else InProcessDavid(settings))
        self.goliath = goliath or goliath_variant(settings)

    async def side(self, name: Side, text: str, direction: str, reference: str | None) -> dict[str, Any]:
        t0 = time.perf_counter()
        if name == "david":
            try:
                r = await self.david.translate(text, direction)
            except DavidUnavailable as exc:
                r = {"status": "error", "text": "", "error": str(exc)[:200]}
            status, out, error, model = r["status"], r.get("text", ""), r.get("error"), r.get("model", self.settings.david_model)
        else:
            g = await translate(self.goliath, text, direction, retriever=None, online=True)
            status, out, error, model = g.status, g.text, g.error, g.model
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        closeness = round(chrf_pp(out, reference), 2) if status == "ok" and reference is not None else None
        return {"status": "ok" if status == "ok" else "error", "text": out if status == "ok" else "",
                "latency_ms": latency_ms if status == "ok" else None, "closeness": closeness,
                "error": error, "model": model}

    async def translate_text(self, body: Translation) -> dict[str, Any]:
        import asyncio

        text = body.text.strip()
        if not text:
            raise HTTPException(422, "Escribe una frase para traducir.")
        example = next((e for e in load_examples() if e["pair_id"] == body.example), None) if body.example else None
        if example is not None and (example["text"] != text or example["direction"] != body.direction):
            example = None  # the box was edited after picking the example: it's typed text now
        reference = example["reference"] if example else None
        names: list[Side] = [body.side] if body.side else ["david", "goliath"]
        results = await asyncio.gather(*(self.side(n, text, body.direction, reference) for n in names))
        return {"direction": body.direction, "source_text": text,
                "reference": ({"text": reference, "source": example["source"], "license": example["license"],
                               "url": example["url"]} if example else None),
                **dict(zip(names, results))}


def create_app(settings: Settings | None = None, page: Page | None = None) -> FastAPI:
    settings = settings or get_settings()
    svc = page or Page(settings)
    app = FastAPI(title="Tzij")
    app.state.page = svc

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"ok": True}

    @app.get("/api/info")
    async def info() -> dict[str, Any]:
        return {"david": settings.david_model, "goliath": settings.gemini_model}

    @app.get("/api/david")
    async def david_ready() -> dict[str, Any]:
        return {"ready": await svc.david.health()}

    @app.get("/api/examples")
    async def examples() -> list[dict]:
        return [public(e) for e in load_examples()]

    @app.post("/api/translate")
    async def translate_text(body: Translation) -> dict[str, Any]:
        return await svc.translate_text(body)

    web = settings.web_dir
    if web.exists():
        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    else:
        @app.get("/", include_in_schema=False)
        async def no_web() -> Response:
            return JSONResponse({"detail": "web/out is missing: run `npm run build` in web/."}, status_code=503)

    return app
