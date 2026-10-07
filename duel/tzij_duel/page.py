"""The demo page's service (public Cloud Run): David and Goliath translate the same text side by side.

  /               the page (static export of web/)
  /api/examples   the example phrases, each with its licensed correct translation
  /api/info       model names for the two columns
  /api/david      {"ready": bool}: also wakes David's GPU service when it was asleep
  /api/translate  one side's translation; the page asks for each side on its own so each column
                  fills as soon as its model answers. Each side says how long it took and what it cost:
                  David, the seconds he worked × his GPU instance's price per second; Goliath, his
                  tokens × Gemini's list price of the day.
  /api/evidence   for a typed phrase without a correct translation: the closest human translations in
                  the translation memory and the words of each side that also appear in them

David runs on his own GPU service (david_app.py, private); Goliath is Gemini on Vertex AI, called
from here. Both times are measured here, as the person in front of the page waits them.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from duel_core import chrf_pp

from .david_app import David
from .david_app import Translation as DavidRequest
from .examples import load_examples, public
from .limits import Limits
from .remote import DavidUnavailable, RemoteDavid
from .settings import Settings, david_usd_per_s, gemini_price_on, get_settings
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


class EvidenceRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_PHRASE_CHARS)
    direction: Literal["es-quc", "quc-es"] = "es-quc"
    outputs: dict[str, str] = Field(default_factory=dict)


class InProcessDavid:
    """Tests and MOCK_AI=1: David runs in this process instead of on the GPU service."""

    def __init__(self, settings: Settings) -> None:
        self.david = David(settings)

    async def health(self, timeout_s: float = 4.0) -> bool:
        return True

    async def translate(self, text: str, direction: str) -> dict[str, Any]:
        return await self.david.translate(DavidRequest(text=text, direction=direction))

    async def reference(self, text: str, direction: str) -> dict[str, Any] | None:
        return self.david.evidence.reference(text, direction)

    async def evidence(self, text: str, direction: str, outputs: dict[str, str]) -> dict[str, Any]:
        return self.david.evidence.evidence(text, direction, outputs)


DAVID_CAP_TEXT = "Por hoy David ya se encendió las veces que esta página permite. Vuelve mañana."
GEMINI_CAP_TEXT = "Por hoy se acabaron las traducciones de Goliath en esta página. David sigue traduciendo."


class Page:
    def __init__(self, settings: Settings, *, david: Any = None, goliath: Variant | None = None,
                 limits: Limits | None = None) -> None:
        self.settings = settings
        self.limits = limits or Limits()
        self.david = david or (RemoteDavid(settings.david_url) if settings.david_url else InProcessDavid(settings))
        self.goliath = goliath or goliath_variant(settings)
        self._references: dict[tuple[str, str], dict | None] = {}

    async def reference_for(self, text: str, direction: str) -> dict[str, Any] | None:
        """The licensed correct translation of a typed phrase, when it exists (asked once per phrase)."""
        key = (direction, text)
        if key not in self._references:
            try:
                self._references[key] = await self.david.reference(text, direction)
            except DavidUnavailable:
                return None
            if len(self._references) > 2000:
                self._references.pop(next(iter(self._references)))
        return self._references[key]

    async def side(self, name: Side, text: str, direction: str, reference: str | None) -> dict[str, Any]:
        t0 = time.perf_counter()
        if name == "david" and not self.limits.start_check():
            return {"status": "error", "text": "", "latency_ms": None, "closeness": None, "cost": None,
                    "error": DAVID_CAP_TEXT, "model": self.settings.david_model}
        if name == "david":
            try:
                r = await self.david.translate(text, direction)
                self.limits.end_check(r.get("status") == "ok")
            except DavidUnavailable as exc:
                r = {"status": "error", "text": "", "error": str(exc)[:200]}
            status, out, error, model = r["status"], r.get("text", ""), r.get("error"), r.get("model", self.settings.david_model)
            # David's GPU instance bills by the second while it's up: the seconds he worked on this one.
            gpu_s = round((r.get("latency_ms") or 0) / 1000, 2)
            cost = {"usd": round(gpu_s * david_usd_per_s(self.settings), 7), "gpu_seconds": gpu_s,
                    "usd_per_hour": round(david_usd_per_s(self.settings) * 3600, 2)}
        elif not self.limits.gemini_call():
            return {"status": "error", "text": "", "latency_ms": None, "closeness": None, "cost": None,
                    "error": GEMINI_CAP_TEXT, "model": self.settings.gemini_model}
        else:
            g = await translate(self.goliath, text, direction, retriever=None, online=True)
            status, out, error, model = g.status, g.text, g.error, g.model
            inp, outp = gemini_price_on(self.settings, date.today())
            cost = {"usd": round((g.input_tokens * inp + g.output_tokens * outp) / 1_000_000, 7),
                    "tokens": g.input_tokens + g.output_tokens}
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        closeness = round(chrf_pp(out, reference), 2) if status == "ok" and reference is not None else None
        return {"status": "ok" if status == "ok" else "error", "text": out if status == "ok" else "",
                "latency_ms": latency_ms if status == "ok" else None, "closeness": closeness,
                "cost": cost if status == "ok" else None, "error": error, "model": model}

    async def translate_text(self, body: Translation) -> dict[str, Any]:
        import asyncio

        text = body.text.strip()
        if not text:
            raise HTTPException(422, "Escribe una frase para traducir.")
        example = next((e for e in load_examples() if e["pair_id"] == body.example), None) if body.example else None
        if example is not None and (example["text"] != text or example["direction"] != body.direction):
            example = None  # the box was edited after picking the example: it's typed text now
        if example:
            found: dict | None = {"text": example["reference"], "source": example["source"],
                                  "license": example["license"], "url": example["url"], "where": "ejemplo"}
        else:  # typed: measured only if the phrase itself is in the licensed data
            found = await self.reference_for(text, body.direction)
        reference = found["text"] if found else None
        names: list[Side] = [body.side] if body.side else ["david", "goliath"]
        results = await asyncio.gather(*(self.side(n, text, body.direction, reference) for n in names))
        return {"direction": body.direction, "source_text": text, "reference": found, **dict(zip(names, results))}


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
        inp, outp = gemini_price_on(settings, date.today())
        return {"david": settings.david_model, "goliath": settings.gemini_model,
                "david_usd_per_hour": round(david_usd_per_s(settings) * 3600, 2),
                "gemini_usd_per_m": {"input": inp, "output": outp}}

    def client_ip(request: Request) -> str:
        # Cloud Run puts the visitor's address first in X-Forwarded-For.
        forwarded = request.headers.get("x-forwarded-for", "")
        return forwarded.split(",")[0].strip() or (request.client.host if request.client else "?")

    @app.get("/api/david")
    async def david_ready(request: Request) -> dict[str, Any]:
        ip = client_ip(request)
        if not svc.limits.allow(ip, "check"):
            raise HTTPException(429, "Demasiadas consultas seguidas: espera un momento.")
        if not svc.limits.keep_alive(ip):
            # A page left open: stop keeping David awake. The next translation wakes him again.
            return {"ready": False, "resting": True}
        if not svc.limits.start_check():
            return {"ready": False, "capped": True}
        ready = await svc.david.health()
        svc.limits.end_check(ready)
        return {"ready": ready}

    @app.get("/api/examples")
    async def examples() -> list[dict]:
        return [public(e) for e in load_examples()]

    @app.post("/api/translate")
    async def translate_text(body: Translation, request: Request) -> dict[str, Any]:
        ip = client_ip(request)
        if not svc.limits.allow(ip, "translate"):
            raise HTTPException(429, "Demasiadas traducciones seguidas: espera un minuto y vuelve a intentar.")
        svc.limits.translated(ip)
        return await svc.translate_text(body)

    @app.post("/api/evidence")
    async def evidence(body: EvidenceRequest) -> dict[str, Any]:
        try:
            return await svc.david.evidence(body.text.strip(), body.direction, body.outputs)
        except DavidUnavailable as exc:
            raise HTTPException(503, "David no responde; intenta de nuevo.") from exc

    web = settings.web_dir
    if web.exists():
        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    else:
        @app.get("/", include_in_schema=False)
        async def no_web() -> Response:
            return JSONResponse({"detail": "web/out is missing: run `npm run build` in web/."}, status_code=503)

    return app
