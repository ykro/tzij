"""FastAPI duel service. Serves the API, the live event stream and the built web views.

  /presentador   presenter screen (1920x1080, laptop / projector)
  /validar       validator screen (the native speaker's phone, over the LAN)
  /api/...       rounds, verdicts, state, events

One process, one origin: the phone only needs the laptop's LAN address, and
everything keeps working with Wi-Fi off (Goliath shows as offline).
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from duel_core import Connectivity, OllamaClient
from rag.retrieve import Retriever

from .deck import Deck
from .events import PRESENTER, VALIDATOR, Broadcaster
from .lan import public_url
from .model_card import model_card
from .rounds import EVALUATION, LIVE, VERDICTS, RoundStore
from .settings import Settings, get_settings
from .variants import Variant, stage_variants, translate

MAX_PHRASE_CHARS = 280


LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def presenter_only(request: Request) -> None:
    """The service listens on the LAN so the phone can vote, but only the laptop drives the show.

    Starting rounds, resetting, toggling Wi-Fi and reading the full state (model names, cost,
    references) are restricted to requests from the laptop itself; the presenter view runs
    there. The phone gets the blind validator stream and the verdict endpoint, nothing else.
    """
    host = request.client.host if request.client else ""
    if host not in LOCAL_HOSTS:
        raise HTTPException(403, "Solo desde la laptop del presentador.")


class StaticOnline:
    """Mock mode: no probing, online unless 'Wi-Fi off' is simulated."""

    def __init__(self, force_offline: bool) -> None:
        self.force_offline = force_offline

    async def is_online(self) -> bool:
        return not self.force_offline


class NewRound(BaseModel):
    kind: Literal["evaluacion", "en_vivo"]
    direction: Literal["es-quc", "quc-es"] = "es-quc"
    text: str | None = Field(default=None, max_length=MAX_PHRASE_CHARS)
    # Specialty round: a phrase from the niche (evals/niche.md: a Pontoon product held out as a
    # translation-memory test). Always Spanish -> K'iche', the direction the niche measures.
    specialty: bool = False


class Verdict(BaseModel):
    slot: int = Field(ge=0, le=1)
    verdict: Literal["correcta", "aceptable", "incorrecta"]
    voter: str = Field(min_length=4, max_length=64)


class ConnectivityToggle(BaseModel):
    force_offline: bool


class Service:
    def __init__(self, settings: Settings, *, david: Variant | None = None, goliath: Variant | None = None,
                 retriever: Retriever | None = None, connectivity: Any = None, deck: Deck | None = None) -> None:
        self.settings = settings
        default_david, default_goliath = stage_variants(settings)
        self.david = david or default_david
        self.goliath = goliath or default_goliath
        self.retriever = retriever if retriever is not None else (
            _mock_retriever(settings) if settings.mock_ai else _load_retriever(settings)
        )
        self.connectivity = connectivity or (
            StaticOnline(settings.force_offline) if settings.mock_ai else Connectivity(force_offline=settings.force_offline)
        )
        self.store = RoundStore(settings.state_path)
        self.deck = deck or (
            Deck(None, test_file=MOCK_DATA / "deck.jsonl", niche_file=MOCK_DATA / "niche.jsonl")
            if settings.mock_ai
            else Deck(settings.processed_dir, require_validated=settings.require_validated_test)
        )
        self.events = Broadcaster(on_change=self._subscribers_changed)
        self.card = model_card(settings)
        self.validator_url = public_url(settings.public_url, settings.port) + "/validar/"
        self.online = True
        self.tasks: set[asyncio.Task] = set()
        self.index_warning = index_mismatch(self.retriever, settings.processed_dir) if not settings.mock_ai else None
        if self.index_warning:
            print(f"!! {self.index_warning}")

    async def refresh_online(self) -> bool:
        online = await self.connectivity.is_online()
        changed = online != self.online
        self.online = online
        if changed:
            self.publish()
        return online

    def state(self) -> dict[str, Any]:
        current = self.store.current
        return {
            "round": current.public() if current else None,
            "scoreboard": self.store.scoreboard(),
            "online": self.online,
            "force_offline": bool(getattr(self.connectivity, "force_offline", False)),
            "contenders": {
                "david": {"label": "David", "model": self.david.model, "retrieval": True, "local": True},
                "goliath": {"label": "Goliath", "model": self.goliath.model, "retrieval": False, "local": False},
            },
            "model_card": self.card,
            "validator_url": self.validator_url,
            "deck_size": len(self.deck.items),
            "niche_deck_size": self.deck.niche_size,
            "mock": self.settings.mock_ai,
            "index_warning": self.index_warning,
            "validators": self.events.count(VALIDATOR),
        }

    def validator_state(self) -> dict[str, Any]:
        current = self.store.current
        return {"round": current.blind() if current else None}

    def _subscribers_changed(self, channel: str) -> None:
        # A validator phone joining or leaving changes what the presenter shows on live rounds.
        if channel == VALIDATOR:
            self.events.publish(PRESENTER, "state", self.state())

    def publish(self) -> None:
        self.events.publish(PRESENTER, "state", self.state())
        self.events.publish(VALIDATOR, "validator", self.validator_state())

    async def run_round(self, round_id: str) -> None:
        round_ = self.store.get(round_id)
        if round_ is None:  # reset before the task started
            return
        online = await self.refresh_online()
        david, goliath = await asyncio.gather(
            translate(self.david, round_.source_text, round_.direction, retriever=self.retriever,
                      online=online, reference=round_.reference),
            translate(self.goliath, round_.source_text, round_.direction, retriever=None,
                      online=online, reference=round_.reference),
        )
        if self.store.set_results(round_id, {"david": david.to_dict(), "goliath": goliath.to_dict()}) is None:
            return  # reset while translating: the results belong to a round that no longer exists
        self.publish()

    def start_round(self, body: NewRound) -> dict[str, Any]:
        if self.store.current and self.store.current.status == "translating":
            raise HTTPException(409, "Hay una ronda en curso.")
        if body.kind == EVALUATION:
            used = {((r.reference_meta or {}).get("pair_id"), r.direction) for r in self.store.rounds}
            specialty = bool(getattr(body, "specialty", False))
            direction = "es-quc" if specialty else body.direction
            item = self.deck.next(direction, used, niche=specialty)
            if item is None:
                what = "de especialidad" if specialty else "de evaluación"
                raise HTTPException(404, f"No quedan frases {what} en esta dirección.")
            meta = {**item.meta(), "specialty": specialty}
            round_ = self.store.create(kind=EVALUATION, direction=item.direction, source_text=item.source_text,
                                       reference=item.reference, reference_meta=meta)
        else:
            text = (body.text or "").strip()
            if not text:
                raise HTTPException(422, "Escribe una frase para la ronda en vivo.")
            round_ = self.store.create(kind=LIVE, direction=body.direction, source_text=text)
        self.publish()
        task = asyncio.create_task(self.run_round(round_.id))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return round_.public()

    def vote(self, round_id: str, body: Verdict) -> dict[str, Any]:
        try:
            round_ = self.store.vote(round_id, body.slot, body.verdict, body.voter)
        except KeyError:
            raise HTTPException(404, "Ronda no encontrada.")
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        self.publish()
        return round_.blind()

    def reset(self) -> None:
        self.store.reset()
        self.deck.reset()
        self.publish()


MOCK_DATA = Path(__file__).resolve().parent.parent / "mock_data"


def _mock_retriever(settings: Settings) -> Retriever:
    """MOCK_AI=1: a tiny index of licensed pairs with hashing embeddings. No Ollama, no `make index`."""
    import json

    from rag.build_index import build
    from rag.embedder import HashingEmbedder

    records = [json.loads(line) for line in (MOCK_DATA / "index_pairs.jsonl").read_text(encoding="utf-8").splitlines()]
    path = settings.state_path.parent / "mock-index.sqlite"
    build(records, HashingEmbedder(), path, "mock")
    return Retriever(path, embedder=HashingEmbedder())


def index_mismatch(retriever: Retriever | None, processed: Path) -> str | None:
    """The index must come from the same dataset version the evals and the model card describe."""
    from .deck import latest_dataset

    dataset = latest_dataset(processed)
    if retriever is None or dataset is None:
        return None
    if retriever.dataset_version != dataset.name:
        return (f"el índice de recuperación es del dataset {retriever.dataset_version}, pero LATEST es "
                f"{dataset.name}: corre `make index`")
    return None


def _load_retriever(settings: Settings) -> Retriever | None:
    try:
        return Retriever(settings.rag_index, mode=settings.rag_mode, order=settings.rag_order, fuzzy=settings.rag_fuzzy,
                         trigram=settings.rag_trigram, select=settings.rag_select)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"!! retrieval disabled: {exc}")
        return None


def create_app(settings: Settings | None = None, service: Service | None = None) -> FastAPI:
    settings = settings or get_settings()
    svc = service or Service(settings)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        async def watch_connectivity() -> None:
            while True:
                with contextlib.suppress(Exception):
                    await svc.refresh_online()
                await asyncio.sleep(3)

        watcher = asyncio.create_task(watch_connectivity())
        if not settings.mock_ai and isinstance(svc.david.client, OllamaClient):
            # Load David with the same context size the rounds use (a different num_ctx reloads
            # the model), and the embedding model too: a cold load costs seconds on stage.
            with contextlib.suppress(Exception):
                import httpx

                async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=120) as http:
                    await http.post("/api/chat", json={"model": svc.david.model, "messages": [], "keep_alive": "2h",
                                                       "options": {"num_ctx": settings.ollama_num_ctx}})
                if svc.retriever:
                    await asyncio.to_thread(svc.retriever.retrieve, "hola", "es-quc", 1)
        yield
        watcher.cancel()

    app = FastAPI(title="Tzij duel", lifespan=lifespan)
    app.state.service = svc

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "online": svc.online, "retrieval": svc.retriever is not None, "mock": settings.mock_ai}

    local = [Depends(presenter_only)]

    @app.get("/api/state", dependencies=local)
    async def state() -> dict[str, Any]:
        return svc.state()

    @app.get("/api/validator")
    async def validator() -> dict[str, Any]:
        return svc.validator_state()

    @app.get("/api/events")
    async def events(request: Request, view: Literal["presenter", "validator"] = "presenter") -> StreamingResponse:
        import json

        if view == PRESENTER:
            presenter_only(request)
        first_event = "state" if view == PRESENTER else "validator"
        first_data = svc.state() if view == PRESENTER else svc.validator_state()
        first = f"event: {first_event}\ndata: {json.dumps(first_data, ensure_ascii=False)}\n\n"
        return StreamingResponse(svc.events.stream(view, first), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/rounds", dependencies=local)
    async def new_round(body: NewRound) -> dict[str, Any]:
        return svc.start_round(body)

    @app.post("/api/rounds/{round_id}/verdicts")
    async def verdict(round_id: str, body: Verdict) -> dict[str, Any]:
        return svc.vote(round_id, body)

    @app.get("/api/suggestions", dependencies=local)
    async def suggestions(direction: Literal["es-quc", "quc-es"] = "es-quc") -> list[dict]:
        return svc.deck.suggestions(direction)

    @app.post("/api/connectivity", dependencies=local)
    async def connectivity(body: ConnectivityToggle) -> dict[str, Any]:
        """Rehearsal switch: simulate Wi-Fi off for Goliath without touching the OS."""
        svc.connectivity.force_offline = body.force_offline
        if hasattr(svc.connectivity, "_cached"):
            svc.connectivity._cached = None
        await svc.refresh_online()
        svc.publish()
        return {"online": svc.online, "force_offline": body.force_offline}

    @app.post("/api/reset", dependencies=local)
    async def reset() -> dict[str, Any]:
        svc.reset()
        return {"ok": True}

    @app.get("/api/verdicts")
    async def verdict_options() -> list[str]:
        return list(VERDICTS)

    web: Path = settings.web_dir
    if web.exists():
        @app.get("/", include_in_schema=False)
        async def root() -> RedirectResponse:
            return RedirectResponse("/presentador/")

        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    else:
        @app.get("/", include_in_schema=False)
        async def no_web() -> JSONResponse:
            return JSONResponse({"detail": "Web views not built: run `make web`."}, status_code=503)

    return app
